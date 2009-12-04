from Acquisition import aq_inner, aq_parent
from zope import schema
from zope.interface import implements
import zope.component

from z3c.form import validator
from z3c.form import error

from plone.dexterity import content
from plone.directives import form
from opengever.repository import _
from opengever.repository.interfaces import IRepositoryFolder
from plone.app.content.interfaces import INameFromTitle
from five import grok
from plone.app.layout.viewlets.interfaces import IBelowContentTitle
from plone.memoize.instance import memoize

class IRepositoryFolderSchema(form.Schema):
    """ A Repository Folder
    """

    form.fieldset(
        u'common',
        label = _(u'fieldset_common', default=u'Common'),
        fields = [
            u'effective_title',
            u'reference_number',
            u'description',
            ],
        )

    #form.omitted('title')
    form.order_before(effective_title = '*')
    effective_title = schema.TextLine(
        title = _(u'Title'),
        required = True
        )

    reference_number = schema.Int(
        title = _(u'label_reference_number', default=u'Reference'),
        description = _(u'help_reference_number', default=u''),
        required = False,
        min = 1,
        )

    description = schema.Text(
        title = _(u'label_description', default=u'Description'),
        description =  _(u'help_description', default=u'A short summary of the content.'),
        required = False,
        )

@form.default_value(field=IRepositoryFolderSchema['reference_number'])
def reference_number_default_value(data):
    highest_reference_number = 0
    for obj in data.context.listFolderContents():
        if IRepositoryFolder.providedBy(obj):
            if obj.reference_number > highest_reference_number:
                highest_reference_number = obj.reference_number
    highest_reference_number += 1
    return highest_reference_number


class ReferenceNumberValidator(validator.SimpleFieldValidator):
    """
    Reference number is uniqe per container (folder).
    """
    def validate(self, value):
        super(ReferenceNumberValidator, self).validate(value)
        if '++add++' in self.request.get('PATH_TRANSLATED', object()):
            # context is container
            siblings = self.context.getFolderContents(full_objects=1)
        else:
            parent = self.context.aq_inner.aq_parent
            siblings = filter(lambda a:a!=self.context, parent.getFolderContents(full_objects=1))
        sibling_ref_nums = []
        for sibling in siblings:
            try:
                sibling_ref_nums.append(self.field.get(sibling))
            except AttributeError:
                pass
        if value in sibling_ref_nums:
            raise schema.interfaces.ConstraintNotSatisfied()

validator.WidgetValidatorDiscriminators(
    ReferenceNumberValidator,
    field=IRepositoryFolderSchema['reference_number']
    )
zope.component.provideAdapter(ReferenceNumberValidator)
zope.component.provideAdapter(error.ErrorViewMessage(
        _('error_sibling_reference_number_existing', default=u'A Sibling with the same reference number is existing'),
        error = schema.interfaces.ConstraintNotSatisfied,
        field = IRepositoryFolderSchema['reference_number'],
        ),
                              name = 'message'
                              )


class RepositoryFolder(content.Container):

    implements(IRepositoryFolder)
    def Title(self):
        title = u' %s' % self.effective_title
        obj = self
        while IRepositoryFolder.providedBy(obj):
            if hasattr(obj, 'reference_number'):
                title = unicode(obj.reference_number) + '.' + title
            obj = aq_parent(aq_inner(obj))
        return title

    def allowedContentTypes(self, *args, **kwargs):
        types = super(RepositoryFolder, self).allowedContentTypes(*args, **kwargs)
        # check if self contains any similar objects
        contains_similar_objects = False
        for id, obj in self.contentItems():
            if obj.portal_type==self.portal_type:
                contains_similar_objects = True
                break
        # get fti of myself
        fti = self.portal_types.get(self.portal_type)
        # filter content types, if required
        if contains_similar_objects:
            # only allow same types
            types = filter(lambda a:a==fti, types)
        return types



class NameFromTitle(grok.Adapter):
    """ An INameFromTitle adapter for namechooser
    gets the name from effective_title
    """
    grok.implements(INameFromTitle)
    grok.context(IRepositoryFolder)

    def __init__(self, context):
        self.context = context

    @property
    def title(self):
        return self.context.effective_title

class Byline(grok.Viewlet):
    grok.viewletmanager(IBelowContentTitle)
    grok.context(IRepositoryFolder)
    grok.name("plone.belowcontenttitle.documentbyline")

    #update = content.DocumentBylineViewlet.update

    @memoize
    def workflow_state(self):
        pw = self.context.portal_workflow
        return pw.getStatusOf(pw.getChainFor(self.context)[0], self.context)['review_state']
