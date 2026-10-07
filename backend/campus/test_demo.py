import json
import tempfile
from datetime import date
from io import StringIO
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.db import DatabaseError
from django.utils import timezone
from rest_framework.test import APIClient
from .models import CampusPlace, Entrance, Block, Room


class DemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_campus', stdout=StringIO(), stderr=StringIO())
        cls.user = get_user_model().objects.create_user(email='demo-test@example.com', password='Demo-Test-927!')

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.user)

    def make_place(self, **values):
        return CampusPlace.objects.create(slug='test-facility', name='Test facility', category='OTHER', aliases=['Special place'], **values)

    def test_place_search_normalization_pagination_and_unmapped_location(self):
        p = self.make_place(description='A test description.', floor=0)
        data = self.client.get('/api/campus/search/', {'q': '  special   PLACE ', 'page_size': 1}).json()
        self.assertEqual(data['count'], 1)
        item = data['results'][0]
        self.assertEqual(item['id'], p.pk)
        self.assertEqual(item['floor'], 0)
        self.assertIsNone(item['block'])
        self.assertFalse(item['map_available'])
        selection = self.client.get('/api/campus/location/', {'type': 'place', 'id': p.pk}).json()
        self.assertIsNone(selection['map']['block_code'])
        self.assertIsNone(selection['map']['entrance_code'])
        self.assertEqual(self.client.get('/api/campus/location/', {'type': 'place', 'id': 'bad'}).status_code, 400)
        self.assertEqual(self.client.get('/api/campus/location/', {'type': 'place', 'id': 999999}).status_code, 404)

    def test_metadata_alone_does_not_bind_place_and_explicit_map_works(self):
        p = self.make_place(block=Block.objects.get(code='E'))
        data = self.client.get('/api/campus/location/', {'type':'place', 'id':p.pk}).json()
        self.assertIsNone(data['map']['block_code'])
        p.map_element='block:E'; p.save()
        self.assertEqual(self.client.get('/api/campus/location/', {'type':'place','id':p.pk}).json()['map']['block_code'], 'E')
        p.map_element='block:F'
        with self.assertRaises(ValidationError): p.full_clean()

    def test_validation_keeps_room_rules_and_verification(self):
        p = self.make_place()
        for field, value in [('map_element','made-up'), ('floor',5), ('aliases','bad'), ('verification_status','VERIFIED')]:
            old = getattr(p, field); setattr(p, field, value)
            with self.assertRaises(ValidationError): p.full_clean()
            setattr(p, field, old)
        p.room=Room.objects.get(code='E204'); p.floor=1
        with self.assertRaises(ValidationError): p.full_clean()

    def test_catalog_all_eight_rooms_and_actual_links(self):
        data=self.client.get('/api/campus/catalog/').json()
        self.assertEqual(len(data['barrels']),8)
        d2=next(r for r in data['barrels'] if r['barrel_label']=='D2')
        self.assertEqual(d2['code'],'E221')
        selection=self.client.get('/api/campus/location/', {'type':'room','id':d2['id']}).json()
        self.assertEqual((selection['map']['block_code'],selection['map']['barrel_code'],selection['map']['entrance_code']),('E','D','MAIN'))
        Room.objects.filter(code='D117').delete()
        self.assertFalse(any(p['type']=='room' for p in self.client.get('/api/campus/catalog/').json()['quick_places']))

    def test_entrance_descriptions_update_repeat_and_preserve_manual(self):
        g=Entrance.objects.get(code='G')
        self.assertEqual(g.description,'Located between Blocks G and H.')
        self.assertEqual(self.client.get('/api/campus/location/', {'type':'entrance','code':'G'}).json()['description'],g.description)
        self.assertEqual(self.client.get('/api/campus/search/', {'q':'H'}).json()['results'][0]['entrance']['description'],g.description)
        g.description='Manually checked entrance'; g.save()
        out=StringIO();err=StringIO()
        call_command('update_campus_details',stdout=out,stderr=err)
        g.refresh_from_db(); self.assertEqual(g.description,'Manually checked entrance')
        self.assertIn('Conflict',err.getvalue())
        call_command('update_campus_details',stdout=out,stderr=err)
        g.refresh_from_db(); self.assertEqual(g.description,'Manually checked entrance')

    def test_anonymous_expired_and_catalog_error(self):
        self.client.logout()
        for url in ['/api/campus/catalog/','/api/campus/search/?q=E204','/api/campus/location/?type=place&id=1']:
            self.assertEqual(self.client.get(url).status_code,401)
        self.client.force_login(self.user)
        from django.contrib.sessions.models import Session
        Session.objects.filter(session_key=self.client.cookies['sessionid'].value).update(expire_date=timezone.now())
        self.assertEqual(self.client.get('/api/campus/catalog/').status_code,401)
        self.client.force_login(self.user)
        with patch('campus.catalog_views.Room.objects.filter',side_effect=DatabaseError):
            self.assertEqual(self.client.get('/api/campus/catalog/').status_code,503)

    def test_affiliation_staff_has_no_admin_access(self):
        self.user.profile_type='STAFF'; self.user.verified_affiliation='STAFF'
        self.user.university_email='demo-staff@sdu.edu.kz';self.user.affiliation_verified_at=timezone.now();self.user.affiliation_source='EMAIL';self.user.save()
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.client.get('/admin/campus/campusplace/add/').status_code,302)
        admin=get_user_model().objects.create_superuser(email='demo-admin@example.com',password='Demo-admin-927!')
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/admin/campus/campusplace/add/').status_code,200)

    def row(self, **values):
        return dict(slug='import-test',name='Verified test place',category='OTHER',source='Test survey',verification_status='VERIFIED',verified_at='2026-10-07',**values)

    def run_import(self, rows, **options):
        with tempfile.NamedTemporaryFile('w',suffix='.json') as f:
            json.dump({'version':1,'places':rows},f);f.flush()
            call_command('import_campus_places',f.name,stdout=StringIO(),**options)

    def test_import_dry_run_repeat_invalid_and_conflict_atomic(self):
        self.run_import([self.row()],dry_run=True)
        self.assertFalse(CampusPlace.objects.exists())
        self.run_import([self.row()]);self.run_import([self.row()])
        self.assertEqual(CampusPlace.objects.count(),1)
        p=CampusPlace.objects.get();p.description='Manual edit';p.save()
        row=self.row(description='Replacement')
        with self.assertRaises(CommandError): self.run_import([row])
        p.refresh_from_db();self.assertEqual(p.description,'Manual edit')
        self.run_import([row],update=True,dry_run=True)
        p.refresh_from_db();self.assertEqual(p.description,'Manual edit')
        self.run_import([row],update=True)
        p.refresh_from_db();self.assertEqual(p.description,'Replacement')
        for bad in [self.row(floor=6), self.row(map_element='invented'), self.row(aliases='wrong'), dict(self.row(),verification_status='UNVERIFIED'), dict(self.row(),block='Z')]:
            with self.assertRaises(CommandError): self.run_import([dict(self.row(),slug='first-new'),bad])
            self.assertFalse(CampusPlace.objects.filter(slug='first-new').exists())
        with self.assertRaises(CommandError): self.run_import([self.row(),self.row()])

    def test_place_related_metadata_has_constant_queries(self):
        for n in range(4):
            CampusPlace.objects.create(slug=f'place-{n}', name=f'Survey place {n}',category='OTHER',room=Room.objects.get(code='E204'))
        self.client.force_authenticate(self.user)
        with self.assertNumQueries(6):
            response=self.client.get('/api/campus/search/', {'q':'Survey place'})
        self.assertEqual(response.json()['count'],4)
