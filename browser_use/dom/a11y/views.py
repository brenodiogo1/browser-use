from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# Enums for DOM types
class NodeType(int, Enum):
	"""DOM node types based on the DOM specification."""

	ELEMENT_NODE = 1
	ATTRIBUTE_NODE = 2
	TEXT_NODE = 3
	CDATA_SECTION_NODE = 4
	ENTITY_REFERENCE_NODE = 5
	ENTITY_NODE = 6
	PROCESSING_INSTRUCTION_NODE = 7
	COMMENT_NODE = 8
	DOCUMENT_NODE = 9
	DOCUMENT_TYPE_NODE = 10
	DOCUMENT_FRAGMENT_NODE = 11
	NOTATION_NODE = 12


# Base models
class BackendNode(BaseModel):
	"""Backend node with a friendly name."""

	nodeType: NodeType = Field(description="Node's nodeType")
	nodeName: str = Field(description="Node's nodeName")
	backendNodeId: int = Field(description='Backend node identifier')


class AXRelatedNode(BaseModel):
	"""A related accessibility node."""

	backendDOMNodeId: int | None = Field(None, description='The BackendNodeId of the related DOM node')
	idref: str | None = Field(None, description='The IDRef value provided, if any')
	text: str | None = Field(None, description='The text alternative of this node in the current context')


class AXValueSource(BaseModel):
	"""A single source for a computed AX property."""

	type: str = Field(description='What type of source this is')
	value: Optional['AXValue'] = Field(None, description='The value of this property source')
	attribute: str | None = Field(None, description='The name of the relevant attribute, if any')
	attributeValue: Optional['AXValue'] = Field(None, description='The value of the relevant attribute, if any')
	superseded: bool | None = Field(None, description='Whether this source is superseded by a higher priority source')
	nativeSource: str | None = Field(None, description='The native markup source for this value')
	nativeSourceValue: Optional['AXValue'] = Field(None, description='The value of the native source')
	invalid: bool | None = Field(None, description='Whether the value for this property is invalid')
	invalidReason: str | None = Field(None, description='Reason for the value being invalid, if it is')


class AXValue(BaseModel):
	"""A single computed AX property."""

	type: str = Field(description='The type of this value')
	value: Any | None = Field(None, description='The computed value of this property')
	relatedNodes: list[AXRelatedNode] | None = Field(None, description='One or more related nodes, if applicable')
	sources: list[AXValueSource] | None = Field(
		None, description='The sources which contributed to the computation of this property'
	)


class AXProperty(BaseModel):
	"""An accessibility property."""

	name: str = Field(description='The name of this property')
	value: AXValue = Field(description='The value of this property')


class AXNode(BaseModel):
	"""A node in the accessibility tree."""

	nodeId: str = Field(description='Unique identifier for this node')
	ignored: bool = Field(description='Whether this node is ignored for accessibility')
	ignoredReasons: list[AXProperty] | None = Field(None, description='Collection of reasons why this node is hidden')
	role: AXValue | None = Field(None, description="This Node's role, whether explicit or implicit")
	chromeRole: AXValue | None = Field(None, description="This Node's Chrome raw role")
	name: AXValue | None = Field(None, description='The accessible name for this Node')
	description: AXValue | None = Field(None, description='The accessible description for this Node')
	value: AXValue | None = Field(None, description='The value for this Node')
	properties: list[AXProperty] | None = Field(None, description='All other properties')
	parentId: str | None = Field(None, description="ID for this node's parent")
	childIds: list[str] | None = Field(None, description="IDs for each of this node's child nodes")
	backendDOMNodeId: int | None = Field(None, description='The backend ID for the associated DOM node, if any')
	frameId: str | None = Field(None, description='The frame ID for the frame associated with this nodes document')


class DOMNode(BaseModel):
	"""A DOM node."""

	nodeId: int = Field(description='Node identifier')
	parentId: int | None = Field(None, description='The id of the parent node if any')
	backendNodeId: int = Field(description='The BackendNodeId for this node')
	nodeType: NodeType = Field(description="Node's nodeType")
	nodeName: str = Field(description="Node's nodeName")
	localName: str = Field(description="Node's localName")
	nodeValue: str = Field(description="Node's nodeValue")
	childNodeCount: int | None = Field(None, description='Child count for Container nodes')
	children: list['DOMNode'] | None = Field(None, description='Child nodes of this node when requested with children')
	attributes: list[str] | None = Field(
		None, description='Attributes of the Element node in the form of flat array [name1, value1, name2, value2]'
	)
	documentURL: str | None = Field(None, description='Document URL that Document or FrameOwner node points to')
	baseURL: str | None = Field(None, description='Base URL that Document or FrameOwner node uses for URL completion')
	publicId: str | None = Field(None, description="DocumentType's publicId")
	systemId: str | None = Field(None, description="DocumentType's systemId")
	internalSubset: str | None = Field(None, description="DocumentType's internalSubset")
	xmlVersion: str | None = Field(None, description="Document's XML version in case of XML documents")
	name: str | None = Field(None, description="Attr's name")
	value: str | None = Field(None, description="Attr's value")
	pseudoType: str | None = Field(None, description='Pseudo element type for this node')
	pseudoIdentifier: str | None = Field(None, description='Pseudo element identifier for this node')
	shadowRootType: str | None = Field(None, description='Shadow root type')
	frameId: str | None = Field(None, description='Frame ID for frame owner elements')
	contentDocument: Optional['DOMNode'] = Field(None, description='Content document for frame owner elements')
	shadowRoots: list['DOMNode'] | None = Field(None, description='Shadow root list for given element host')
	templateContent: Optional['DOMNode'] = Field(None, description='Content document fragment for template elements')
	pseudoElements: list['DOMNode'] | None = Field(None, description='Pseudo elements associated with this node')
	importedDocument: Optional['DOMNode'] = Field(None, description='Deprecated: imported document for HTMLImport links')
	distributedNodes: list[BackendNode] | None = Field(None, description='Distributed nodes for given insertion point')
	isSVG: bool | None = Field(None, description='Whether the node is SVG')
	compatibilityMode: str | None = Field(None, description='Document compatibility mode')
	assignedSlot: BackendNode | None = Field(None, description='Assigned slot for this node')
	isScrollable: bool | None = Field(None, description='Whether the node is scrollable')


# Response models
class AccessibilityTreeResponse(BaseModel):
	"""Response from Chrome DevTools Protocol Accessibility.getFullAXTree."""

	nodes: list[AXNode] = Field(description='List of accessibility nodes')


class DOMTreeResponse(BaseModel):
	"""Response from get_entire_dom_tree method."""

	root: DOMNode = Field(description='The root DOM node')
	nodes: dict[int, DOMNode] = Field(description='Dictionary of nodeId to DOM node')
	total_nodes: int = Field(description='Total number of nodes in the tree')
	frame_count: int = Field(description='Number of frames encountered')


# Enable forward references
DOMNode.model_rebuild()
AXValue.model_rebuild()
AXValueSource.model_rebuild()
