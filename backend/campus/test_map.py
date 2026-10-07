from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Block, Entrance, Room


class MapLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_campus', stdout=StringIO())
        cls.user = get_user_model().objects.create_user(email='map-tests@example.com', password='Map-Tests-927!')

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def select(self, kind, **params):
        return self.client.get('/api/campus/location/', {'type': kind, **params})

    def room(self, code):
        response = self.select('room', id=Room.objects.get(code=code).pk)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_e204_and_h_room_use_real_block_entrance(self):
        e = self.room('E204')
        self.assertEqual(e['floor'], 2)
        self.assertEqual(e['map']['block_code'], 'E')
        self.assertEqual(e['map']['entrance_code'], 'MAIN')
        self.assertIsNone(e['map']['barrel_code'])
        self.assertTrue(e['provisional'])
        h = self.room('H204')
        self.assertEqual(h['map']['block_code'], 'H')
        self.assertEqual(h['map']['entrance_code'], 'G')

    def test_barrel_d2_is_e221_not_block_d(self):
        data = self.room('E221')
        self.assertEqual(data['map']['block_code'], 'E')
        self.assertEqual(data['map']['barrel_code'], 'D')
        self.assertEqual(data['map']['barrel_label'], 'D2')
        self.assertEqual(data['map']['entrance_code'], 'MAIN')
        response = self.client.get('/api/campus/search/', {'q': 'Barrel D2'})
        self.assertEqual(response.data['results'][0]['id'], data['id'])

    def test_all_barrels_follow_aliases(self):
        for code, label in [('D117','A1'), ('D218','A2'), ('D116','B1'), ('D217','B2'),
                            ('D113','C1'), ('D214','C2'), ('E117','D1'), ('E221','D2')]:
            with self.subTest(code=code):
                self.assertEqual(self.room(code)['map']['barrel_label'], label)

    def test_individual_entrance_and_absence_have_priority(self):
        room = Room.objects.get(code='E204')
        room.recommended_entrance = Entrance.objects.get(code='I')
        room.save()
        data = self.room('E204')
        self.assertEqual(data['map']['entrance_code'], 'I')
        self.assertTrue(data['map']['entrance_position_provisional'])
        self.assertEqual(data['entrance']['status'], 'UNKNOWN')
        room.recommended_entrance = None
        room.save()
        Block.objects.filter(code='E').update(recommended_entrance=None)
        self.assertIsNone(self.room('E204')['map']['entrance_code'])

    def test_blocks_and_standalone_entrances(self):
        for block, entry in [('D','MAIN'),('E','MAIN'),('F','MAIN'),('G','G'),('H','G'),('I','I')]:
            data = self.select('block', code=block.lower()).data
            self.assertEqual(data['map']['entrance_code'], entry)
            self.assertNotIn('floor', data)
        for code in ['MAIN','G','I']:
            data = self.select('entrance', code=code).data
            self.assertEqual(data['map']['entrance_code'], code)
            self.assertIsNone(data['map']['block_code'])

    def test_context_blocks_do_not_create_inventory(self):
        count = Block.objects.count(), Room.objects.count()
        for code in 'ABC':
            data = self.select('block', code=code).data
            self.assertTrue(data['map']['context_only'])
            self.assertEqual(data['map']['block_code'], code)
            self.assertIsNone(data['map']['entrance_code'])
        self.assertEqual((Block.objects.count(), Room.objects.count()), count)

    def test_unknown_ids_and_validation_do_not_create_records(self):
        count = Room.objects.count()
        self.assertEqual(self.select('room', id=9999999999).status_code, 404)
        self.assertEqual(self.select('block', code='Z').status_code, 404)
        self.assertEqual(self.select('entrance', code='Z').status_code, 404)
        for kind, params in [('room',{}),('room',{'id':'-1'}),('room',{'id':'x'}),('room',{'id':'9'*50}),
                             ('invalid',{}),('block',{'code':'x'*81})]:
            self.assertEqual(self.select(kind, **params).status_code, 400)
        self.assertEqual(Room.objects.count(), count)

    def test_anonymous_session_and_cache_headers(self):
        response = self.select('block', code='E')
        self.assertIn('no-store', response['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.select('block', code='E').status_code, 401)

    def test_no_n_plus_one_and_database_errors(self):
        room_id = Room.objects.get(code='E204').pk
        self.client.force_authenticate(self.user)
        with self.assertNumQueries(1):
            self.select('room', id=room_id)
        with patch('django.db.models.query.QuerySet.get', side_effect=DatabaseError):
            self.assertEqual(self.select('block', code='E').status_code, 503)

    def test_unconfirmed_barrel_alias_is_not_a_guessed_coordinate(self):
        room = Room.objects.get(code='E221')
        room.name = 'Lecture theatre'
        room.aliases = []
        room.save()
        self.assertIsNone(self.room('E221')['map']['barrel_code'])
