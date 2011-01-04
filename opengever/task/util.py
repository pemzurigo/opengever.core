from five import grok
import AccessControl
from zope.annotation.interfaces import IAnnotations
from zope.schema.interfaces import IContextSourceBinder, ISource
from zope.schema.vocabulary import SimpleVocabulary

from Products.CMFCore.utils import getToolByName
from Products.CMFPlone import PloneMessageFactory as PMF

from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from collective.elephantvocabulary import wrap_vocabulary
from opengever.task.interfaces import ITaskSettings

import opengever.task


class UsersVocabulary(SimpleVocabulary):

    def search(self, query_string):
        return [v for v in self if query_string.lower() in v.value.lower()]


@grok.provider(IContextSourceBinder)
def getManagersVocab(context):

    acl_users = getToolByName(context, 'acl_users')
    terms = []
    if acl_users is not None:
        for user in acl_users.getUsers():
            member_name = user.getProperty('fullname') or user.getName()
            member_name = member_name + "  " + user.getProperty('email') or member_name

            terms.append(SimpleVocabulary.createTerm(user.getId(),
            str(user.getId()),
            member_name))
    return UsersVocabulary(terms)


@grok.provider(IContextSourceBinder)
def getTransitionVocab(context):
    if AccessControl.getSecurityManager().getUser() == AccessControl.SpecialUsers.nobody:
        return SimpleVocabulary([])
    wftool = getToolByName(context, 'portal_workflow')
    transitions = []
    if opengever.task.task.ITask.providedBy(context) and context.REQUEST.URL.find('++add++opengever.task.task') == -1:
        for tdef in wftool.getTransitionsFor(context):
            transitions.append(SimpleVocabulary.createTerm(tdef['id'],
            tdef['id'],
            PMF(tdef['id'],
            default=tdef['title_or_id'])))
        return SimpleVocabulary(transitions)
    else:
        wf = wftool.get(wftool.getChainForPortalType('opengever.task.task')[0])
        state = wf.states.get(wf.initial_state)
        for tid in state.transitions:
            tdef= wf.transitions.get(tid, None)
            transitions.append(SimpleVocabulary.createTerm(tdef.id,
            tdef.id,
            PMF(tdef.id, default=tdef.title_or_id)))
        return SimpleVocabulary(transitions)


def create_sequence_number(obj, key='task_sequence_number'):
    portal = obj.portal_url.getPortalObject()
    portal_annotations = IAnnotations(portal)
    sequence_number = int(portal_annotations.get(key, 0)) + 1
    portal_annotations[key] = sequence_number
    return sequence_number


@grok.provider(IContextSourceBinder)
def getTaskTypeVocabulary(context):
    terms = []
    for task_type in ['unidirectional_by_reference',
                      'unidirectional_by_value',
                      'bidirectional_by_reference',
                      'bidirectional_by_value']:
        for term in wrap_vocabulary('opengever.task.'+task_type,
                visible_terms_from_registry=\
                    'opengever.task.interfaces.ITaskSettings.' + \
                        task_type)(context):
            terms.append(term)
    return SimpleVocabulary(terms)
