from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Block, Entrance, Room


class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_campus', stdout=StringIO())
        cls.user = get_user_model().objects.create_user(email='search@example.com', password='Search-Test-927!')

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def search(self, query, **params):
        return self.client.get('/api/campus/search/', {'q': query, **params})

    def first(self, query):
        response = self.search(query)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['results'][0]

    def test_room_code_case_and_spacing(self):
        for query in ['E204', 'e204', '  e 204  ', 'Е204']:
            with self.subTest(query=query):
                room = self.first(query)
                self.assertEqual(room['code'], 'E204')
                self.assertEqual(room['floor'], 2)
                self.assertEqual(room['block']['code'], 'E')
                self.assertEqual(room['entrance']['code'], 'MAIN')

    def test_aliases_are_room_names_not_block_codes(self):
        self.assertEqual(self.first(' a1 ')['code'], 'D117')
        for query in ['Бочка D2', 'бочка   d2']:
            room = self.first(query)
            self.assertEqual(room['code'], 'E221')
            self.assertEqual(room['block']['code'], 'E')
            self.assertFalse(room['provisional'])

    def test_partial_and_name_search(self):
        response = self.search('E2')
        codes = [r['code'] for r in response.data['results']]
        self.assertIn('E204', codes)
        self.assertIn('E221', codes)
        room = Room.objects.get(code='E204')
        room.name = '  Physics   laboratory  '
        room.save()
        self.assertEqual(self.first('physics')['code'], 'E204')
        self.assertEqual(self.first('physics  laboratory')['code'], 'E204')

    def test_exact_alias_ranks_before_partial_code(self):
        room = Room.objects.get(code='D117')
        room.aliases += ['E2']
        room.save()
        self.assertEqual(self.first('E2')['code'], 'D117')

    def test_blocks_and_h_entrance(self):
        for query in ['E', 'Блок E', 'блок  e']:
            result = self.first(query)
            self.assertEqual(result['type'], 'block')
            self.assertEqual(result['code'], 'E')
            self.assertNotIn('floor', result)
        block = self.first('H')
        self.assertEqual(block['entrance']['code'], 'G')
        self.assertEqual(block['entrance']['status'], 'USER_REPORTED')

    def test_provisional_data_and_unknown_kind(self):
        room = self.first('I401')
        self.assertTrue(room['provisional'])
        self.assertIn('Сгенерировано', room['source'])
        self.assertEqual(room['kind'], 'UNKNOWN')
        self.assertEqual(room['entrance']['status'], 'PROVISIONAL')
        self.assertEqual(self.first('G')['entrance']['status'], 'PROVISIONAL')

    def test_room_entrance_override_does_not_inherit_block_confidence(self):
        room = Room.objects.get(code='E204')
        room.recommended_entrance = Entrance.objects.get(code='I')
        room.save()
        result = self.first('E204')
        self.assertEqual(result['entrance']['code'], 'I')
        self.assertEqual(result['entrance']['status'], 'UNKNOWN')

    def test_unknown_room_does_not_create_inventory(self):
        before = Room.objects.count()
        for query in ['E999', 'I02']:
            self.assertEqual(self.search(query).data['count'], 0)
        self.assertEqual(Room.objects.count(), before)

    def test_anonymous_and_expired_sessions(self):
        self.client.logout()
        self.assertEqual(self.search('E204').status_code, 401)

    def test_empty_limits_literal_wildcards_and_pagination(self):
        self.assertEqual(self.search('  ').data['results'], [])
        self.assertEqual(self.search('x' * 81).status_code, 400)
        for params in [{'page': 0}, {'page': 101}, {'page': 'x'}, {'page_size': 51}, {'page_size': 0}]:
            self.assertEqual(self.search('E', **params).status_code, 400)
        first = self.search('E', page_size=3).data
        second = self.search('E', page_size=3, page=2).data
        self.assertEqual(len(first['results']), 3)
        self.assertEqual(first['next_page'], 2)
        self.assertEqual(first['count'], 23)
        keys = lambda data: {(r['type'], r['id']) for r in data['results']}
        self.assertFalse(keys(first) & keys(second))
        self.assertEqual(self.search('E', page=100).data['results'], [])
        self.assertEqual(self.search('%').data['results'], [])
        self.assertEqual(self.search('_').data['results'], [])

    def test_related_data_does_not_issue_n_plus_one_queries(self):
        self.client.force_authenticate(self.user)
        with self.assertNumQueries(4):
            response = self.search('E', page_size=50)
        self.assertEqual(response.status_code, 200)

    def test_database_failure_is_retryable(self):
        with patch('django.db.models.query.QuerySet.count', side_effect=DatabaseError):
            self.assertEqual(self.search('E204').status_code, 503)

    def test_manual_alias_whitespace_and_unknown_source(self):
        room = Room.objects.get(code='E204')
        room.aliases = ['\tУчебный   зал\t']
        room.source = ''
        room.save()
        result = self.first(' учебный  зал ')
        self.assertEqual(result['code'], 'E204')
        self.assertTrue(result['provisional'])
