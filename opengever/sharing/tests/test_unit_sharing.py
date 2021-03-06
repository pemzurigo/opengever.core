from Products.CMFDefault.MembershipTool import MembershipTool
from mocker import ANY
from opengever.ogds.base.interfaces import IContactInformation
from opengever.sharing.behaviors import IDossier
from opengever.sharing.browser.sharing import OpengeverSharingView
from opengever.sharing.interfaces import ISharingConfiguration
from plone.app.workflow.interfaces import ISharingPageRole
from plone.mocktestcase import MockTestCase
from plone.registry.interfaces import IRegistry
from zope.interface import directlyProvides


class TestOpengeverSharing(MockTestCase):
    """ Tests for sharing.py
    """

    def test_available_roles_dossier_provided(self):
        """ Test available roles from a dossier
        """
        results = self.base_available_roles(IDossier)

        self.assertTrue(len(results) == 1)

        ids = [r.get('id') for r in results]
        self.assertTrue('Reader' in ids)

    def test_available_roles_standard(self):
        """ Test available roles from a standard contenttype
        """
        results = self.base_available_roles()

        self.assertTrue(len(results) == 1)

        ids = [r.get('id') for r in results]
        self.assertTrue('Reader' in ids)

    def base_available_roles(self, provide=""):
        """ Test available_roles mehtod from OpengeverSharingView class
        """
        # Context
        context = self.create_dummy()
        if provide:
            directlyProvides(context, provide)

        mock_context = self.mocker.proxy(context)

        # Request
        request = self.create_dummy()
        mock_request = self.mocker.proxy(request)

        # Sharing view
        sharing = OpengeverSharingView(mock_context, mock_request)
        mock_sharing = self.mocker.patch(sharing)
        self.expect(mock_sharing.roles()).result(
            [{'id':'Reader', }, ]).count(0, None)

        self.replay()

        return sharing.available_roles()

    def test_roles_with_check_permission(self):
        """ Test roles method with permission-check
        """
        pairs = self.base_roles(True)

        self.assertTrue(len(pairs) == 1)

        ids = [p.get('id') for p in pairs]
        self.assertTrue('Reader' in ids)

    def test_roles_without_check_permission(self):
        """ Test roles method without permission-check
        """
        pairs = self.base_roles(False)

        self.assertTrue(len(pairs) == 2)

        ids = [p.get('id') for p in pairs]
        self.assertTrue('Reader' in ids)

    def base_roles(self, check_permission):
        """ Test roles method of OpengeverSharingView class
        """
        # Context
        mock_context = self.mocker.mock(count=False)

        # Request
        request = self.create_dummy()
        mock_request = self.mocker.proxy(request)

        # Membership Tool
        mtool = MembershipTool()
        mock_mtool = self.mocker.proxy(mtool, spec=None, count=False)
        self.expect(mock_mtool.checkPermission(
            'Sharing page: Delegate Reader role', ANY)).result(True)
        self.expect(mock_mtool.checkPermission(
            'Sharing page: Delegate roles', ANY)).result(False)
        self.mock_tool(mock_mtool, 'portal_membership')

        # SharingPageRole Utility 1
        utility1 = self.mocker.mock(count=False)
        self.expect(utility1.required_permission).result(
            'Sharing page: Delegate Reader role')
        self.expect(utility1.title).result('utility_1')

        self.mock_utility(utility1, ISharingPageRole, 'Reader')

        # SharingPageRole Utility 2
        utility2 = self.mocker.mock(count=False)
        self.expect(utility2.required_permission).result(
            'Sharing page: Delegate roles')
        self.expect(utility2.title).result('utility_2')

        self.mock_utility(utility2, ISharingPageRole, 'Administrator')

        self.replay()

        # Sharing view
        sharing = OpengeverSharingView(mock_context, mock_request)

        return sharing.roles(check_permission)

    def test_role_settings_as_manager(self):
        """ Test role_settings logged in with manager-role
        """
        results = self.base_role_settings(['Manager'])

        self.assertTrue(len(results) == 3)
        self.assertTrue(
            'AuthenticatedUsers' in [r.get('id') for r in results])

    def test_role_settings_as_user(self):
        """ Test role_settings logged in with user-role
        """
        results = self.base_role_settings(['User'])

        self.assertTrue(len(results) == 2)
        self.assertTrue(
            not 'AuthenticatedUsers' in [r.get('id') for r in results])

    def test_principal_search_results(self):
        # Context
        context = self.create_dummy()
        mock_context = self.mocker.proxy(context)

        # Request
        request = self.create_dummy()
        mock_request = self.mocker.proxy(request)

        # Sharing view
        _principal_search_results = self.mocker.replace(
            'plone.app.workflow.browser.sharing.SharingView._principal_search_results')

        #contact info mock
        utility_mock = self.mocker.mock()
        self.mock_utility(utility_mock, IContactInformation)

        #registry mock
        registry_mock = self.mocker.mock()
        self.mock_utility(registry_mock, IRegistry)
        reg_proxy_mock = self.mocker.mock()
        self.expect(
            registry_mock.forInterface(ISharingConfiguration)).result(reg_proxy_mock)

        self.expect(reg_proxy_mock.black_list_prefix).result(u'^og_').count(0, None)
        self.expect(reg_proxy_mock.white_list_prefix).result(u'^og_ska-arch').count(0, None)

        user1 = self.create_dummy(userid='sb2m1')
        user2 = self.create_dummy(userid='sb1m1')

        self.expect(utility_mock.list_assigned_users()).result([user1, user2])

        self.expect(
            _principal_search_results(ANY, ANY, ANY, ANY, ANY, ANY)).result(
            [{'type': 'user', 'id': 'sb2m1', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Sachbearbeiter2 Mandant1'},
             {'type': 'user', 'id': 'sb1m1', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Sachbearbeiter1 Mandant1'},
             {'type': 'user', 'id': 'sb1m2', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Leitung1 Mandant1'},
             {'type': 'user', 'id': 'sb2m2', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Sekretariat1 Mandant1'},
             {'type': 'group', 'id': 'other_group', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Administrator1 Mandant1'},
             {'type': 'group', 'id': 'og_ska-arch_users', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Users of SKA ARCH'},
             {'type': 'group', 'id': 'og_bd-arp_users', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Users of BD.ARP'},
             {'type': 'group', 'id': 'og_bd-arp_og_ska-arch-users', 'roles': {u'Publisher': False, u'Administrator': False, u'Editor': False, u'Reader': False, u'Contributor': False, u'Reviewer': False}, 'title': 'Users of BD.ARP'},
             ])

        self.replay()

        sharing = OpengeverSharingView(mock_context, mock_request)
        principals = sharing._principal_search_results(
            None, None, None, None, None)

        # the wrapper shouldn't return the users wich aren't assigned to this client.
        # and also the groups from other og cliens shouldn't be returned.
        self.assertTrue(
            [principal.get('id') for principal in principals],
            ['sb2m1', 'sb1m1', 'other_group', 'og_ska-arch_users'])

    def base_role_settings(self, roles):
        """ Test role_settings method of OpengeverSharingView class
        """
        result_existing = \
            [{'disabled': False,
              'type': 'group',
              'id': 'AuthenticatedUsers',
              'roles': {},
              'title': u'Logged-in users'}, ]
        result_group = \
             [{'disabled': False,
              'type': 'group',
              'id': u'og_mandant1_users',
              'roles': {},
              'title': 'og_mandant1_users'}, ]
        result_user = \
             [{'disabled': False,
              'type': 'user',
              'id': u'og_ska-arch_leitung',
              'roles': {},
              'title': u'og_ska-arch_leitung'}, ]

        # Member
        member = list('member')
        mock_member = self.mocker.proxy(member, spec=False)
        self.expect(mock_member.getRolesInContext(ANY)).result(roles)

        # Context
        mock_context = self.mocker.mock(count=False)
        self.expect(mock_context.__parent__).result(mock_context)
        self.expect(
            mock_context.portal_membership.getAuthenticatedMember()).result(
                mock_member)

        # Request
        request = self.create_dummy()
        mock_request = self.mocker.proxy(request)
        self.expect(mock_request.form).result({})

        # Sharing view
        sharing = OpengeverSharingView(mock_context, mock_request)
        mock_sharing = self.mocker.patch(sharing, spec=False)
        self.expect(
            mock_sharing.existing_role_settings()).result(result_existing)
        self.expect(mock_sharing.user_search_results()).result(result_group)
        self.expect(mock_sharing.group_search_results()).result(result_user)

        self.replay()

        return mock_sharing.role_settings()

