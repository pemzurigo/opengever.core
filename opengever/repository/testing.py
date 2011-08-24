from opengever.ogds.base.setuphandlers import create_sql_tables
from opengever.ogds.base.setuphandlers import _create_example_client
from opengever.ogds.base.utils import create_session
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import PLONE_FIXTURE
from zope.configuration import xmlconfig
from plone.app.testing import TEST_USER_ID, TEST_USER_NAME
from plone.app.testing import setRoles, login

class RepositoryFunctionalLayer(PloneSandboxLayer):
    """Layer for integration tests."""

    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):

        from opengever.ogds.base import setuphandlers
        setuphandlers.setup_scriptable_plugin = lambda *a, **kw: None

        from plone.app import dexterity
        xmlconfig.file('meta.zcml', package=dexterity, context=configurationContext)
        xmlconfig.file('configure.zcml', package=dexterity, context=configurationContext)

        from opengever.ogds import base
        xmlconfig.file('tests.zcml', package=base, context=configurationContext)

        from opengever import repository
        xmlconfig.file('configure.zcml', package=repository, context=configurationContext)

        from ftw import tabbedview
        xmlconfig.file('configure.zcml', package=tabbedview, context=configurationContext)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'ftw.tabbedview:default')
        applyProfile(portal, 'opengever.repository:default')
        applyProfile(portal, 'plone.app.dexterity:default')

        create_sql_tables()
        session = create_session()

        _create_example_client(session, 'plone',
                              {'title': 'Plone',
                              'ip_address': '127.0.0.1',
                              'site_url': 'http://nohost/plone',
                              'public_url': 'http://nohost/plone',
                              'group': 'og_mandant1_users',
                              'inbox_group': 'og_mandant1_inbox'})

        setRoles(portal, TEST_USER_ID, ['Member', 'Reviewer', 'Manager'])

OPENGEVER_REPOSITORY_FIXTURE = RepositoryFunctionalLayer()
OPENGEVER_REPOSITORY_INTEGRATION_TESTING = FunctionalTesting(
    bases=(OPENGEVER_REPOSITORY_FIXTURE, ),
    name="OpengeverRepository:Integration")