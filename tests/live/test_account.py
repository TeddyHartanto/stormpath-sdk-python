"""Live tests of Accounts and authentication functionality."""

from datetime import datetime

from stormpath.error import Error

from .base import AccountBase
from stormpath.resources.application import ApplicationList


class TestAccountGet(AccountBase):

    def test_account_has_applications(self):
        _, account = self.create_account(self.app.accounts)

        self.assertTrue(hasattr(account, 'applications'))
        self.assertTrue(isinstance(account.applications, ApplicationList))
        self.assertEqual(len(account.applications), 1)
        self.assertEqual(account.applications[0].href, self.app.href)


class TestAccountCreateUpdateDelete(AccountBase):

    def test_application_account_creation(self):
        name, acc = self.create_account(self.app.accounts)

        accs = self.app.accounts.query(username=name)

        self.assertEqual(len(accs), 1)
        self.assertEqual(accs[0].username, name)

        dir_accs = self.dir.accounts.query(username=name)

        self.assertEqual(len(dir_accs), 1)
        self.assertEqual(dir_accs[0].username, name)

        accs[0].delete()
        self.assertEqual(len(self.app.accounts.query(username=name)), 0)

    def test_directory_account_creation(self):
        name, acc = self.create_account(self.dir.accounts)

        dir_accs = self.dir.accounts.query(username=name)

        self.assertEqual(len(dir_accs), 1)
        self.assertEqual(dir_accs[0].username, name)

        accs = self.app.accounts.query(username=name)

        self.assertEqual(len(accs), 1)
        self.assertEqual(accs[0].username, name)

        dir_accs[0].delete()
        self.assertEqual(len(self.dir.accounts.query(username=name)), 0)

    def test_duplicate_username_acc_creation_fails(self):
        name, acc = self.create_account(self.app.accounts)

        with self.assertRaises(Error):
            self.create_account(self.app.accounts, username=name)

    def test_duplicate_email_acc_creation_fails(self):
        self.create_account(self.app.accounts, email='foo@example.com')

        with self.assertRaises(Error):
            self.create_account(self.app.accounts, email='foo@example.com')

    def test_account_modification(self):
        name, acc = self.create_account(self.app.accounts)

        acc.email = 'foo@example.com'
        acc.status = acc.STATUS_DISABLED
        acc.save()

        accs = self.app.accounts.query(email=acc.email)

        self.assertEqual(len(accs), 1)
        self.assertFalse(accs[0].is_enabled())

    def test_account_modification_with_custom_data(self):
        name, acc = self.create_account(self.app.accounts)

        acc = self.app.accounts.get(acc.href)

        acc.email = 'foo@example.com'
        acc.status = acc.STATUS_DISABLED
        acc.custom_data['key'] = 'value'
        acc.save()

        accs = self.app.accounts.query(email=acc.email)

        self.assertEqual(len(accs), 1)
        acc = accs[0]
        self.assertEqual(acc.email, 'foo@example.com')
        self.assertEqual(acc.custom_data['key'], 'value')
        self.assertFalse(accs[0].is_enabled())

    def test_account_modification_with_custom_data_and_refresh(self):
        name, acc = self.create_account(self.app.accounts)
        old_email = acc.email

        acc = self.app.accounts.get(acc.href)

        acc.email = 'foo@example.com'
        acc.status = acc.STATUS_DISABLED
        acc.refresh()
        acc.custom_data['key'] = 'value'
        acc.save()

        accs = self.app.accounts.query(email=acc.email)

        self.assertEqual(len(accs), 1)
        acc = accs[0]
        self.assertEqual(acc.email, old_email)
        self.assertEqual(acc.custom_data['key'], 'value')
        self.assertTrue(accs[0].is_enabled())


class TestApplicationAuthentication(AccountBase):

    def setUp(self):
        super(TestApplicationAuthentication, self).setUp()
        self.email = self.get_random_name() + '@example.com'
        self.password = 'W00t123!' + self.get_random_name()
        self.username, self.acc = self.create_account(self.app.accounts,
            email=self.email, password=self.password)

    def test_authentication_via_email_succeeds(self):
        result = self.app.authenticate_account(self.email, self.password)
        self.assertEqual(result.account.href, self.acc.href)

    def test_authentication_via_username_succeeds(self):
        result = self.app.authenticate_account(self.username, self.password)
        self.assertEqual(result.account.href, self.acc.href)

    def test_authentication_failure(self):
        with self.assertRaises(Error):
            self.app.authenticate_account(self.username, 'x')


class TestPasswordReset(AccountBase):

    def setUp(self):
        super(TestPasswordReset, self).setUp()
        self.email = 'some@email.com'
        _, self.acc = self.create_account(self.app.accounts, email=self.email)

    def test_password_reset_workflow(self):
        token = self.app.password_reset_tokens.create({'email': self.email})
        self.assertEqual(token.account.href, self.acc.href)

        acc = self.app.verify_password_reset_token(token.token)
        self.assertEqual(acc.href, self.acc.href)

        new_pwd = 'W00t123!' + self.get_random_name()

        self.app.reset_account_password(token.token, new_pwd)

        auth = self.app.authenticate_account(self.acc.username, new_pwd)
        self.assertEqual(auth.account.href, self.acc.href)

    def test_send_password_reset_email(self):
        account = self.app.send_password_reset_email(self.email)
        self.assertEqual(account.href, self.acc.href)


class TestAccountGroups(AccountBase):

    def test_resolve_group(self):
        _, account = self.create_account(self.app.accounts)

        group = account.directory.groups.create({'name': 'test_group'})

        self.assertEqual(account._resolve_group(group).href, group.href)
        self.assertEqual(account._resolve_group(group.href).href, group.href)
        self.assertEqual(account._resolve_group(group.name).href, group.href)
        self.assertEqual(account._resolve_group({'name': group.name}).href, group.href)
        self.assertEqual(account._resolve_group({'name': '*' + group.name + '*'}).href, group.href)

    def test_add_groups(self):
        _, account = self.create_account(self.app.accounts)

        group1 = account.directory.groups.create({'name': 'test_group'})
        group2 = account.directory.groups.create({'name': 'test_group2'})

        account.add_groups([group1, group2.href])

        self.assertTrue(account.has_group(group1))
        self.assertTrue(account.has_group(group2))

    def test_in_group(self):
        _, account = self.create_account(self.app.accounts)

        group1 = account.directory.groups.create({'name': 'test_group'})
        account.add_group(group1)
        self.assertTrue(account.in_group(group1))

    def test_in_groups(self):
        _, account = self.create_account(self.app.accounts)

        group1 = account.directory.groups.create({'name': 'test_group'})
        group2 = account.directory.groups.create({'name': 'test_group2'})

        account.add_groups([group1, group2])
        self.assertTrue(account.in_groups([group1, group2.href]))

    def test_remove_groups(self):
        _, account = self.create_account(self.app.accounts)

        group1 = account.directory.groups.create({'name': 'test_group'})
        group2 = account.directory.groups.create({'name': 'test_group2'})
        group3 = account.directory.groups.create({'name': 'test_group3'})

        account.add_groups([group1, group2])
        self.assertTrue(account.in_groups([group1, group2.href]))

        account.remove_groups([group1, group2])

        self.assertFalse(account.in_groups([group1, group2]))
        self.assertFalse(account.in_group(group3))

        self.assertRaises(Error, account.remove_groups, [group3])


class TestAccountProviderData(AccountBase):

    def test_account_provider_data_get_exposed_readonly_timestamp_attrs(self):
        name, acc = self.create_account(self.app.accounts)
        pd = acc.provider_data

        self.assertEqual(pd.created_at, pd['created_at'])
        self.assertIsInstance(pd.created_at, datetime)
        self.assertEqual(pd.modified_at, pd['modified_at'])
        self.assertIsInstance(pd.modified_at, datetime)

    def test_account_provider_data_modify_exposed_readonly_timestamps(self):
        name, acc = self.create_account(self.app.accounts)
        pd = acc.provider_data

        with self.assertRaises(AttributeError):
            pd.created_at = 'whatever'
        with self.assertRaises(AttributeError):
            pd['created_at'] = 'whatever'
        with self.assertRaises(AttributeError):
            pd.modified_at = 'whatever'
        with self.assertRaises(AttributeError):
            pd['modified_at'] = 'whatever'

        with self.assertRaises(Exception):
            del pd['created_at']
        with self.assertRaises(Exception):
            del pd['modified_at']
