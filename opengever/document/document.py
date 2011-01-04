from Acquisition import aq_inner
from Products.CMFCore.utils import getToolByName
from Products.MimetypesRegistry.common import MimeTypeException
from ZODB.POSException import ConflictError
from collective import dexteritytextindexer
from collective.elephantvocabulary import wrap_vocabulary
from datetime import datetime
from five import grok
from ftw.datepicker.widget import DatePickerFieldWidget
from opengever.base.interfaces import IReferenceNumber, ISequenceNumber
from opengever.document import _
from opengever.document.interfaces import ICheckinCheckoutManager
from opengever.ogds.base.interfaces import IContactInformation
from opengever.tabbedview.browser.tabs import OpengeverTab
from opengever.tabbedview.browser.tabs import Tasks
from plone.app.dexterity.behaviors.metadata import IBasic
from plone.app.iterate.interfaces import IWorkingCopy
from plone.app.layout.viewlets.interfaces import IBelowContentTitle
from plone.app.versioningbehavior.behaviors import IVersionable
from plone.autoform.interfaces import OMITTED_KEY
from plone.dexterity.content import Item
from plone.directives import form, dexterity
from plone.directives.dexterity import DisplayForm
from plone.i18n.normalizer.interfaces import IIDNormalizer
from plone.indexer import indexer
from plone.namedfile.field import NamedFile
from plone.namedfile.interfaces import INamedFileField
from plone.supermodel.interfaces import FIELDSETS_KEY
from plone.supermodel.model import Fieldset
from plone.z3cform.textlines.textlines import TextLinesFieldWidget
from z3c.form.browser import checkbox
from zc.relation.interfaces import ICatalog
from zope import schema
from zope.app.intid.interfaces import IIntIds
from zope.component import getUtility, queryMultiAdapter, getAdapter
from zope.interface import invariant, Invalid, Interface
from zope.lifecycleevent.interfaces import IObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent
import logging


LOG = logging.getLogger('opengever.document')

# move and omit the changeNote,
# because it's not possible to make a new version when you editing a file
IVersionable.setTaggedValue(FIELDSETS_KEY, [
        Fieldset( 'common', fields=[
                'changeNote',
                ])
        ] )

# TODO: Not Work in plone 4 and the dexterity b2 release
# possibly it can be solved with plone.directives
IVersionable.setTaggedValue(OMITTED_KEY, [
        (Interface, 'changeNote', 'true'),
        ]
)


def related_document(context):
    intids = getUtility( IIntIds )
    return intids.getId( context )


class IDocumentSchema(form.Schema):
    """ Document Schema Interface
    """

    form.fieldset(
        u'common',
        label = _(u'fieldset_common', u'Common'),
        fields = [
            u'title',
            u'description',
            u'keywords',
            u'foreign_reference',
            u'document_date',
            u'receipt_date',
            u'delivery_date',
            u'document_type',
            u'document_author',
            u'file',
            u'paper_form',
            u'preserved_as_paper',
            u'archival_file',
            u'thumbnail',
            ]
        )

    dexteritytextindexer.searchable('title')
    title = schema.TextLine(
        title = _(u'label_title', default=u'Title'),
        required=False)

    dexteritytextindexer.searchable('description')
    description = schema.Text(
        title=_(u'label_description', default=u'Description'),
        description = _(u'help_description', default=u''),
        required = False,
        )

    dexteritytextindexer.searchable('keywords')
    keywords = schema.Tuple(
        title = _(u'label_keywords', default=u'Keywords'),
        description = _(u'help_keywords', default=u''),
        value_type = schema.TextLine(),
        required = False,
        missing_value = (),
        )
    form.widget(keywords = TextLinesFieldWidget)

    foreign_reference = schema.TextLine(
        title = _(u'label_foreign_reference', default='Foreign Reference'),
        description = _('help_foreign_reference', default=''),
        required = False,
        )

    document_date = schema.Date(
        title = _(u'label_document_date', default='Document Date'),
        description = _(u'help_document_date', default=''),
        required = True,
        )
    #workaround because ftw.datepicker wasn't working
    form.widget(document_date = DatePickerFieldWidget)

    document_type = schema.Choice(
        title=_(u'label_document_type', default='Document Type'),
        description=_(u'help_document_type', default=''),
        source=wrap_vocabulary('opengever.document.document_types',
                    visible_terms_from_registry='opengever.document' + \
                            '.interfaces.IDocumentType.document_types'),
        required = False,
        )

    dexteritytextindexer.searchable('document_author')
    document_author = schema.TextLine(
        title=_(u'label_author', default='Author'),
        description=_(u'help_author', default=""),
        required=False,
        )

    dexteritytextindexer.searchable('file')
    form.primary('file')
    file = NamedFile(
        title = _(u'label_file', default='File'),
        description = _(u'help_file', default=''),
        required = False,
        )

    form.widget(paper_form=checkbox.SingleCheckBoxFieldWidget)
    paper_form = schema.Bool(
        title = _(u'label_paper_form', default='Paper form'),
        description = _(u'help_paper_form', default='Available in paper form only'),
        required = False,
        )

    form.widget(preserved_as_paper=checkbox.SingleCheckBoxFieldWidget)
    preserved_as_paper = schema.Bool(
        title = _(u'label_preserved_as_paper', default='Preserved as paper'),
        description = _(u'help_preserved_as_paper', default=''),
        required = False,
        default = True,
        )

    form.omitted('archival_file')
    archival_file = NamedFile(
        title = _(u'label_archival_file', default='Archival File'),
        description = _(u'help_archival_file', default=''),
        required = False,
        )

    form.omitted('thumbnail')
    thumbnail = NamedFile(
        title = _(u'label_thumbnail', default='Thumbnail'),
        description = _(u'help_thumbnail', default=''),
        required = False,
        )

    form.omitted('preview')
    preview = NamedFile(
        title = _(u'label_preview', default='Preview'),
        description = _(u'help_preview', default=''),
        required = False,
        )

    receipt_date = schema.Date(
        title = _(u'label_receipt_date', default='Date of receipt'),
        description = _(u'help_receipt_date', default=''),
        required = False,
        )
    #workaround because ftw.datepicker wasn't working
    form.widget(receipt_date = DatePickerFieldWidget)

    delivery_date = schema.Date(
        title = _(u'label_delivery_date', default='Date of delivery'),
        description = _(u'help_delivery_date', default=''),
        required = False,
        )
    #workaround because ftw.datepicker wasn't working
    form.widget(delivery_date = DatePickerFieldWidget)


    @invariant
    def title_or_file_required(data):
        if not data.title and not data.file:
            raise Invalid(_(u'error_title_or_file_required',
                            default=u'Either the title or the file is '
                            'required.'))

    @invariant
    def file_or_paper_form(data):
        """ Small validator who check:
            paper_form xor file
        """
        if not (data.paper_form ^ bool(data.file)):
            if data.paper_form:
                raise Invalid(
                    _(u'error_paperform_and_file',
                    default=u"You select a file and said is only in paper_form,\
                    please correct it."))
            else:
                raise Invalid(
                    _(u'error_no_paperform_and_no_file',
                    default=u"You don't select a file and also the 'only in paper_form' isn't selected,\
                    please correct it."))

    # TODO: doesn't work with Plone 4
    #form.order_after(**{'IRelatedItems.relatedItems': 'file'})

@form.default_value(field=IDocumentSchema['document_date'])
def documentDateDefaultValue(data):
    """Set today's date as default for document_data"""
    return datetime.today()

@form.default_value(field=IDocumentSchema['document_author'])
def document_author_default_value(data):
    user = data.context.portal_membership.getAuthenticatedMember()
    info = getUtility(IContactInformation)
    user = user.getId()
    if info.is_user(user) or info.is_contact(user):
        return info.describe(user)
    else:
        return user

class Document(Item):

    # disable file preview creation when modifying or creating document
    buildPreview = False

    def Title(self):
        title = Item.Title(self)
        if IWorkingCopy.providedBy(self):
            return '%s (Arbeitskopie)' % title
        return title

    def getIcon(self, relative_to_portal=0):
        """Calculate the icon using the mime type of the file
        """
        surrender = lambda :super(Document, self).getIcon(relative_to_portal=relative_to_portal)
        mtr   = getToolByName(self, 'mimetypes_registry', None)
        utool = getToolByName(self, 'portal_url')

        field = self.file
        if not field or not field.getSize():
            # there is no file
            return surrender()

        # get icon by content type
        contenttype       = field.contentType
        mimetypeitem = None
        try:
            mimetypeitem = mtr.lookup(contenttype)
        except MimeTypeException, msg:
            LOG.error('MimeTypeException for %s. Error is: %s' % (self.absolute_url(), str(msg)))
        if not mimetypeitem:
            # not found
            return surrender()
        icon = mimetypeitem[0].icon_path

        if relative_to_portal:
            return icon
        else:
            # Relative to REQUEST['BASEPATH1']
            res = utool(relative=1) + '/' + icon
            while res[:1] == '/':
                res = res[1:]
            return res

    def icon(self):
        """for ZMI
        """
        return self.getIcon()



@indexer(IDocumentSchema)
def related_items( obj ):
    catalog = getUtility( ICatalog )
    intids = getUtility( IIntIds )
    obj_id = intids.getId( obj )
    results = []
    relations = catalog.findRelations({'to_id' : obj_id, 'from_attribute': 'relatedItems'})
    for rel in relations:
        results.append(rel.from_id)
    return results


grok.global_adapter(related_items, name='related_items')


# SearchableText
class SearchableTextExtender(grok.Adapter):
    grok.context(IDocumentSchema)
    grok.name('IDocumentSchema')
    grok.implements(dexteritytextindexer.IDynamicTextIndexExtender)

    def __init__(self, context):
        self.context = context

    def __call__(self):
        searchable = []
        # append some other attributes to the searchableText index
        # reference_number
        refNumb = getAdapter(self.context, IReferenceNumber)
        searchable.append(refNumb.get_number())

        # sequence_number
        seqNumb = getUtility(ISequenceNumber)
        searchable.append(str(seqNumb.get_number(self.context)))

        return ' '.join(searchable)


# INDEX: document_author
@indexer( IDocumentSchema )
def document_author( obj ):
    context = aq_inner( obj )
    if not context.document_author:
        return None
    return context.document_author
grok.global_adapter( document_author, name='document_author' )


# INDEX: document_date
@indexer( IDocumentSchema )
def document_date( obj ):
    context = aq_inner( obj )
    if not context.document_date:
        return None
    return context.document_date
grok.global_adapter( document_date, name='document_date' )


# INDEX: receipt_date
@indexer( IDocumentSchema )
def receipt_date( obj ):
    context = aq_inner( obj )
    if not context.receipt_date:
        return None
    return context.receipt_date
grok.global_adapter( receipt_date, name='receipt_date' )


# INDEX: delivery_date
@indexer( IDocumentSchema )
def delivery_date( obj ):
    context = aq_inner( obj )
    if not context.delivery_date:
        return None
    return context.delivery_date
grok.global_adapter( delivery_date, name='delivery_date' )

# INDEX: checked_out
@indexer( IDocumentSchema )
def checked_out( obj ):
    manager = queryMultiAdapter((obj, obj.REQUEST), ICheckinCheckoutManager)
    if not manager:
        return ''

    value = manager.checked_out()
    if value:
        return value

    else:
        return ''
grok.global_adapter( checked_out, name='checked_out' )





@grok.subscribe(IDocumentSchema, IObjectCreatedEvent)
@grok.subscribe(IDocumentSchema, IObjectModifiedEvent)
def sync_title_and_filename_handler(doc, event):
    """Syncs the document and the filename (#586):
    o If there is no title but a file, use the filename (without extension) as
    title.
    o If there is a title and a file, use the normalized title as filename
    """
    normalize_method = getUtility(IIDNormalizer).normalize

    if not doc.title and doc.file:
        # use the filename without extension as title
        filename = doc.file.filename
        doc.title = filename[:filename.rfind('.')]

    elif doc.title and doc.file:
        # use the title as filename
        filename = doc.file.filename
        doc.file.filename = normalize_method(doc.title) + \
            filename[filename.rfind('.'):]


class View(dexterity.DisplayForm):
    grok.context(IDocumentSchema)
    grok.require("zope2.View")

    def creator_link(self):
        info = getUtility(IContactInformation)
        return info.render_link(self.context.Creator())

    def author_link(self):
        info = getUtility(IContactInformation)
        return info.render_link(self.context.document_author)


class ForwardViewlet(grok.Viewlet):
    """Display the message subject
    """
    grok.name('opengever.document.ForwardViewlet')
    grok.context(IDocumentSchema)
    grok.require('zope2.View')
    grok.viewletmanager(IBelowContentTitle)

    def render(self):
        if self.request.get("externaledit",None):
            return '<script language="JavaScript">jq(function(){window.location.href="'+str(self.context.absolute_url())+'/external_edit"})</script>'
        return ''


class Overview(DisplayForm, OpengeverTab):
    grok.context(IDocumentSchema)
    grok.name('tabbedview_view-overview')
    grok.template('overview')

    def get_referenced_documents(self):
        pc = self.context.portal_catalog
        return pc({'portal_type':'Document',})

    def creator_link(self):
        info = getUtility(IContactInformation)
        return info.render_link(self.context.Creator())


class RelatedTasks(Tasks):
    grok.context(IDocumentSchema)
    grok.name('tabbedview_view-tasks')

    search_options = {'related_items': related_document}

    def update_config(self):
        Tasks.update_config(self)

        # do not search on this context, search on site
        self.filter_path = None



class DownloadFileVersion(grok.CodeView):
    grok.context(IDocumentSchema)
    grok.name('download_file_version')

    def render(self):
        version_id = self.request.get('version_id')
        pr = self.context.portal_repository
        old_obj = pr.retrieve(self.context, version_id).object
        old_file = old_obj.file
        response = self.request.RESPONSE
        response.setHeader('Content-Type', old_file.contentType)
        response.setHeader('Content-Length', old_file.getSize())
        response.setHeader('Content-Disposition',
                           'attachment;filename="%s"' % old_file.filename)
        return old_file.data