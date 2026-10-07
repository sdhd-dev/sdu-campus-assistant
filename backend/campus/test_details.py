from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .approved_details import BARREL_DETAILS, FACULTIES, FACULTY_SOURCE
from .models import Block, Room


class ApprovedDetailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_campus', stdout=StringIO(), stderr=StringIO())
        cls.user = get_user_model().objects.create_user(email='details-tests@example.com', password='Details-Test-927!')

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def update(self):
        out, err = StringIO(), StringIO()
        call_command('update_campus_details', stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_fresh_seed_has_approved_english_and_only_known_faculties(self):
        for code, alias, old, description in BARREL_DETAILS:
            room = Room.objects.get(code=code)
            self.assertEqual(room.name, f'Barrel {alias}')
            self.assertEqual(room.description, description)
        for code, name in FACULTIES.items():
            block = Block.objects.get(code=code)
            self.assertEqual(block.faculty_name, name)
            self.assertEqual(block.faculty_source, FACULTY_SOURCE)
        for code in 'HI':
            self.assertEqual(Block.objects.get(code=code).faculty_name, '')
        self.assertEqual(Room.objects.count(), 128)

    def test_existing_seed_and_empty_fields_upgraded_idempotently(self):
        for index, (code, alias, legacy, description) in enumerate(BARREL_DETAILS):
            Room.objects.filter(code=code).update(name='' if index == 0 else f'Бочка {alias}',
                                                description='' if index == 1 else legacy)
        Block.objects.update(faculty_name='', faculty_source='')
        structural = lambda: list(Room.objects.order_by('id').values('id','code','block_id','floor','aliases','recommended_entrance_id','source'))
        before = structural()
        out, err = self.update()
        self.assertIn('8 rooms, 4 blocks; 0 conflicts', out)
        self.assertEqual(err, '')
        self.assertEqual(structural(), before)
        self.test_fresh_seed_has_approved_english_and_only_known_faculties()
        out, err = self.update()
        self.assertIn('0 rooms, 0 blocks; 0 conflicts', out)
        self.assertEqual(err, '')
        self.assertEqual(structural(), before)

    def test_manual_corrections_and_source_preserved_with_conflicts(self):
        Room.objects.filter(code='D117').update(name='Custom hall name', description='Manually surveyed description')
        Block.objects.filter(code='D').update(faculty_name='Manual faculty correction', faculty_source='Manual survey')
        out, err = self.update()
        self.assertIn('D117.name', err)
        self.assertIn('D117.description', err)
        self.assertIn('Block D.faculty_name', err)
        room = Room.objects.get(code='D117')
        self.assertEqual(room.description, 'Manually surveyed description')
        self.assertEqual(room.name, 'Custom hall name')
        block = Block.objects.get(code='D')
        self.assertEqual(block.faculty_name, 'Manual faculty correction')
        self.assertEqual(block.faculty_source, 'Manual survey')
        stderr = StringIO()
        call_command('seed_campus', stdout=StringIO(), stderr=stderr)
        room.refresh_from_db()
        self.assertEqual(room.description, 'Manually surveyed description')
        self.assertEqual(Room.objects.count(), 128)
        self.assertIn('D117.description', stderr.getvalue())

    def test_manual_provenance_is_not_silently_reattributed(self):
        Block.objects.filter(code='E').update(faculty_name='', faculty_source='Manual provenance')
        out, err = self.update()
        self.assertIn('Block E.faculty_source', err)
        block = Block.objects.get(code='E')
        self.assertEqual(block.faculty_name, '')
        self.assertEqual(block.faculty_source, 'Manual provenance')

    def test_missing_record_is_reported_not_created(self):
        Room.objects.get(code='D117').delete()
        out, err = self.update()
        self.assertIn('Missing room D117', err)
        self.assertEqual(Room.objects.count(), 127)

    def test_all_barrels_search_and_map_deliver_full_details(self):
        for code, alias, old, description in BARREL_DETAILS:
            for query in [code, alias, f'Barrel {alias}']:
                with self.subTest(query=query):
                    response = self.client.get('/api/campus/search/', {'q':query})
                    self.assertEqual(response.status_code, 200)
                    item = response.data['results'][0]
                    self.assertEqual(item['code'], code)
                    self.assertEqual(item['description'], description)
                    self.assertEqual(item['block']['faculty_name'], FACULTIES[code[0]])
                    self.assertEqual(item['block']['faculty_source'], FACULTY_SOURCE)
                    selected = self.client.get('/api/campus/location/', {'type':'room','id':item['id']}).data
                    self.assertEqual(selected['description'], description)
                    self.assertEqual(selected['block'], item['block'])
                    self.assertEqual(selected['map']['barrel_label'], alias)
                    self.assertEqual(selected['map']['block_code'], code[0])

    def test_room_and_block_faculty_and_faculty_search(self):
        room = self.client.get('/api/campus/search/', {'q':'E204'}).data['results'][0]
        self.assertEqual(room['block']['faculty_name'], FACULTIES['E'])
        for code, faculty in FACULTIES.items():
            response = self.client.get('/api/campus/search/', {'q':faculty.lower()})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            block = response.data['results'][0]
            self.assertEqual(block['type'], 'block')
            self.assertEqual(block['code'], code)
            self.assertEqual(block['block']['faculty_name'], faculty)
        partial = self.client.get('/api/campus/search/', {'q':'Education'}).data
        self.assertEqual(partial['results'][0]['code'], 'E')

    def test_map_label_catalog_uses_same_data_and_session_protection(self):
        self.client.force_authenticate(self.user)
        with self.assertNumQueries(1):
            response = self.client.get('/api/campus/blocks/')
        self.assertEqual(response.status_code, 200)
        blocks = {item['code']:item for item in response.data['blocks']}
        self.assertEqual(set(blocks), set('DEFGHI'))
        self.assertEqual(blocks['E']['faculty_name'], FACULTIES['E'])
        self.assertEqual(blocks['H']['faculty_name'], '')
        self.assertIn('no-store', response['Cache-Control'])
        self.client.force_authenticate(user=None)
        self.client.logout()
        self.assertEqual(self.client.get('/api/campus/blocks/').status_code, 401)
