from datetime import datetime, timedelta
from opengever.dossier.behaviors.dossier import IDossier
from opengever.ogds.base.interfaces import IClientConfiguration
from opengever.tasktemplates.testing \
    import OPENGEVER_TASKTEMPLATES_INTEGRATION_TESTING
from plone.app.testing import SITE_OWNER_NAME
from plone.dexterity.utils import createContent, addContentToContainer
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility
from zope.event import notify
from zope.lifecycleevent import ObjectCreatedEvent, ObjectAddedEvent
import unittest2 as unittest


def create_testobject(parent, ptype, **kwargs):
    createContent(ptype)
    obj = createContent(ptype, **kwargs)
    notify(ObjectCreatedEvent(obj))
    obj = addContentToContainer(parent, obj, checkConstraints=False)
    notify(ObjectAddedEvent(obj))
    return obj


class TestTaskTemplatesIntegration(unittest.TestCase):

    layer = OPENGEVER_TASKTEMPLATES_INTEGRATION_TESTING

    def test_integration(self):
        """ Tests the integration of tasktemplatefolder and
        tasktemplate
        """

        portal = self.layer['portal']
        workflow = getToolByName(portal, 'portal_workflow')
        catalog = getToolByName(portal, 'portal_catalog')
        mtool = getToolByName(portal, 'portal_membership')

        # Set client-name in registry
        getUtility(IRegistry).forInterface(
            IClientConfiguration).client_id = u'plone'

        # Folders and templates
        template_folder_1 = create_testobject(
            portal,
            'opengever.tasktemplates.tasktemplatefolder',
            title='TaskTemplateFolder 1')

        template_folder_2 = create_testobject(
            portal,
            'opengever.tasktemplates.tasktemplatefolder',
            title='TaskTemplateFolder 2')

        template1 = create_testobject(
            template_folder_1,
            'opengever.tasktemplates.tasktemplate',
            title='TaskTemplate 1',
            text='Test Text',
            preselected=True,
            task_type='unidirectional_by_value',
            issuer='responsible',
            responsible_client='interactive_users',
            deadline=7,
            responsible='current_user', )

        template2 = create_testobject(
            template_folder_1,
            'opengever.tasktemplates.tasktemplate',
            title='TaskTemplate 2',
            text='Test Text',
            preselected=False,
            task_type='unidirectional_by_value',
            issuer='responsible',
            responsible_client='zopemaster',
            deadline=7,
            responsible='current_user', )

        template3 = create_testobject(
            template_folder_1,
            'opengever.tasktemplates.tasktemplate',
            title='TaskTemplate 3',
            text='Test Text',
            preselected=False,
            task_type='unidirectional_by_value',
            issuer='responsible',
            responsible_client='interactive_users',
            deadline=7,
            responsible='responsible', )

        # Activate folder 1
        workflow.doActionFor(template_folder_1,
                             'tasktemplatefolder-transition-inactiv-activ')

        dossier = create_testobject(
            portal,
            'opengever.dossier.businesscasedossier',
            title='Dossier 1',
        )
        IDossier(dossier).responsible = SITE_OWNER_NAME

        add_tasktemplate_view = dossier.restrictedTraverse('add-tasktemplate')

        # We just can find folder 1 because folder 2 is inactive
        self.assertTrue(
            template_folder_1.title in add_tasktemplate_view.listing(
                show='templates'))
        self.assertFalse(
            template_folder_2.title in add_tasktemplate_view.listing(
                show='templates'))

        # Activate folder 2
        workflow.doActionFor(template_folder_2,
                             'tasktemplatefolder-transition-inactiv-activ', )

        # Now we can see both
        self.assertTrue(
            template_folder_1.title in add_tasktemplate_view.listing(
                show='templates'))
        self.assertTrue(
            template_folder_2.title in add_tasktemplate_view.listing(
                show='templates'))

        # In folder 1 we can find two tasktemplates
        self.assertTrue(
            template1.title in add_tasktemplate_view.listing(
                show='tasks', path="/".join(
                    template_folder_1.getPhysicalPath())))

        self.assertTrue(
            template2.title in add_tasktemplate_view.listing(
                show='tasks', path="/".join(
                    template_folder_1.getPhysicalPath())))

        # In folder 2 we can't find any tasktemplates
        self.assertFalse(
            template1.title in add_tasktemplate_view.listing(
                show='tasks', path="/".join(
                    template_folder_2.getPhysicalPath())))

        self.assertFalse(
            template2.title in add_tasktemplate_view.listing(
                show='tasks', path="/".join(
                    template_folder_2.getPhysicalPath())))

        # We create a task using the template 1
        add_tasktemplate_view.create(
            paths=["/".join(template1.getPhysicalPath())])

        # We create a task using the template 2
        add_tasktemplate_view.create(
            paths=["/".join(template2.getPhysicalPath())])

        # We create a task using the template 3
        add_tasktemplate_view.create(
            paths=["/".join(template3.getPhysicalPath())])

        # We try to create a task but we abort the transaction
        # so it won't make a new task
        add_tasktemplate_view.request['abort'] = 'yes'
        url = add_tasktemplate_view.create(
            paths=["/".join(template1.getPhysicalPath())])

        # This redirect us to the default dossier view
        self.assertTrue(url == dossier.absolute_url())

        brains = catalog(
            path='/'.join(dossier.getPhysicalPath()),
                portal_type='opengever.task.task')

        # We should have now three Task-Objects
        self.assertTrue(3 == len(brains))

        task = brains[0]

        # Check the attributes from the template
        self.assertTrue(task.Title == template1.title)
        self.assertTrue(
            task.responsible == mtool.getAuthenticatedMember().getId())
        self.assertTrue(
            task.deadline.date() == (datetime.today() + timedelta(
                template1.deadline)).date())
        self.assertTrue(task.getObject().text == template1.text)
        self.assertTrue(task.issuer == IDossier(dossier).responsible)