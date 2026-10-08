from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from .models import CampusPlace, Room

class FacilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_campus',stdout=StringIO(),stderr=StringIO())
        call_command('seed_campus_places',stdout=StringIO(),stderr=StringIO())
        cls.user=get_user_model().objects.create_user(email='facilities-test@example.com',password='Facility-test-927!')

    def setUp(self):
        self.client=APIClient();self.client.force_login(self.user)

    def test_aliases_and_distinct_halls(self):
        for q, slug in [('library','library'),('библиотека','library'),('red hall','red-hall'),('ред холл','red-hall'),('mini red hall','mini-red-hall'),('мини ред холл','mini-red-hall'),('  MINI   RED HALL  ','mini-red-hall')]:
            with self.subTest(query=q):
                results=self.client.get('/api/campus/search/',{'q':q}).json()['results']
                self.assertEqual(results[0]['code'],slug)
                self.assertEqual(results[0]['type'],'place')
        data=self.client.get('/api/campus/search/',{'q':'red hall'}).json()
        self.assertEqual({p['name'] for p in data['results']},{'Red Hall','Mini Red Hall'})

    def test_search_map_and_catalog_share_complete_data(self):
        catalog=self.client.get('/api/campus/catalog/').json()['places']
        self.assertEqual(len(catalog),3)
        for p in catalog:
            selected=self.client.get('/api/campus/location/',{'type':'place','id':p['id']}).json()
            result=self.client.get('/api/campus/search/',{'q':p['name']}).json()['results'][0]
            for field in ['name','description','location','photo','photo_alt','details','map_note','map_element']:
                self.assertEqual(p[field],selected[field]);self.assertEqual(p[field],result[field])
            self.assertIsNone(selected['floor']);self.assertIsNone(selected['block']);self.assertIsNone(selected['entrance']['code'])
            self.assertIsNone(selected['map']['entrance_code'])
            self.assertIsNone(selected['map']['block_code'] if p['code']!='red-hall' else None)
            self.assertTrue(selected['photo'].endswith('.webp'))
        red=next(p for p in catalog if p['code']=='red-hall')
        self.assertEqual(self.client.get('/api/campus/location/',{'type':'place','id':red['id']}).json()['map']['block_code'],'A')
        library=CampusPlace.objects.get(slug='library')
        self.assertEqual(library.details,['Three floors','Separate outdoor entrance'])
        self.assertEqual(library.map_element,'library-area')
        self.assertIsNone(library.recommended_entrance_id)

    def test_repeat_preserves_manual_changes_without_fake_rooms(self):
        before=Room.objects.count();p=CampusPlace.objects.get(slug='library');pk=p.pk
        p.description='Manual checked description';p.photo='';p.save()
        err=StringIO();call_command('seed_campus_places',stdout=StringIO(),stderr=err)
        p.refresh_from_db();self.assertEqual(p.pk,pk);self.assertEqual(p.description,'Manual checked description');self.assertEqual(p.photo,'')
        self.assertIn('Conflict',err.getvalue());self.assertEqual(CampusPlace.objects.count(),3);self.assertEqual(Room.objects.count(),before)

    def test_facility_selection_keeps_existing_inventory_and_auth(self):
        self.assertEqual(self.client.get('/api/campus/search/',{'q':'E204'}).json()['results'][0]['code'],'E204')
        self.assertEqual(self.client.get('/api/campus/search/',{'q':'A1'}).json()['results'][0]['code'],'D117')
        self.client.logout()
        self.assertEqual(self.client.get('/api/campus/location/',{'type':'place','id':CampusPlace.objects.first().pk}).status_code,401)

    def test_photo_paths_and_new_map_bindings_are_validated(self):
        from django.core.exceptions import ValidationError
        p=CampusPlace.objects.get(slug='library')
        for path in ['https://example.com/photo.webp','/campus/places/../private.webp','/campus/places/library.svg']:
            p.photo=path
            with self.assertRaises(ValidationError): p.full_clean()
        p.photo='/campus/places/library.webp';p.photo_alt=''
        with self.assertRaises(ValidationError): p.full_clean()
        p.photo_alt='Library entrance';p.full_clean()
