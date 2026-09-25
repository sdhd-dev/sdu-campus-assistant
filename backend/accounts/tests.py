from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserTests(TestCase):
    def test_email_authentication_and_password_hashing(self):
        user = User.objects.create_user(" Student@SDU.edu.kz ", "test-only-password")
        self.assertEqual(user.email, "student@sdu.edu.kz")
        self.assertNotEqual(user.password, "test-only-password")
        self.assertTrue(user.check_password("test-only-password"))
        self.assertEqual(authenticate(email="STUDENT@sdu.edu.kz", password="test-only-password"), user)
        self.assertIsNone(authenticate(email=user.email, password="wrong-password"))

    def test_profile_types_do_not_grant_privileges(self):
        for profile_type in User.ProfileType.values:
            with self.subTest(profile_type=profile_type):
                user = User.objects.create_user(f"{profile_type}@example.com", profile_type=profile_type)
                user.refresh_from_db()
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertFalse(user.has_usable_password())

    def test_database_rejects_case_insensitive_duplicate_email(self):
        User.objects.create_user("student@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="STUDENT@example.com")

    def test_database_rejects_invalid_profile_type(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("student@example.com", profile_type="ADMIN")

    def test_superuser_flags_are_explicit_and_independent(self):
        user = User.objects.create_superuser("admin@example.com", "test-only-password")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.profile_type, User.ProfileType.VISITOR)
        for flags in ({"is_staff": False}, {"is_superuser": False}):
            with self.assertRaises(ValueError):
                User.objects.create_superuser("invalid@example.com", **flags)

    def test_email_is_required(self):
        for email in (None, "", "   "):
            with self.assertRaises(ValueError):
                User.objects.create_user(email)
