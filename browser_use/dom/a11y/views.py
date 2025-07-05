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

	def has_property(self, property_name: str, value: Any) -> bool:
		if not self.properties:
			return False
		for prop in self.properties:
			if prop.name == property_name and prop.value.value == value:
				return True
		return False


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


# Combined tree types
class CombinedBaseNode(BaseModel):
	"""Base class for combined DOM + Accessibility tree nodes."""

	# DOM properties
	node_id: int = Field(description='DOM node identifier')
	backend_node_id: int = Field(description='Backend node identifier')
	node_type: NodeType = Field(description='DOM node type')
	node_name: str = Field(description='DOM node name')
	node_value: str = Field(description='DOM node value')

	# Accessibility data (None if no accessibility node attached)
	accessibility: AXNode | None = Field(None, description='Accessibility node data if available')

	# Tree structure
	parent: Optional['CombinedBaseNode'] = Field(None, description='Parent node reference', exclude=True)
	children: list['CombinedBaseNode'] = Field(default_factory=list, description='Child nodes')

	# Visibility and state
	is_visible: bool = Field(default=True, description='Whether node is visible')
	is_new: bool | None = Field(None, description='Whether node is new since last state')

	def has_accessibility_data(self) -> bool:
		"""Check if this node has accessibility data attached."""
		return self.accessibility is not None

	def has_parent_with_accessibility(self) -> bool:
		"""Check if any parent node has accessibility data."""
		current = self.parent
		while current:
			if current.has_accessibility_data():
				return True
			current = current.parent
		return False

	def get_accessibility_role(self) -> str | None:
		"""Get the accessibility role if available."""
		if self.accessibility and self.accessibility.role:
			return str(self.accessibility.role.value) if self.accessibility.role.value else None
		return None

	def get_accessibility_name(self) -> str | None:
		"""Get the accessibility name if available."""
		if self.accessibility and self.accessibility.name:
			return str(self.accessibility.name.value) if self.accessibility.name.value else None
		return None

	def get_accessibility_description(self) -> str | None:
		"""Get the accessibility description if available."""
		if self.accessibility and self.accessibility.description:
			return str(self.accessibility.description.value) if self.accessibility.description.value else None
		return None

	def __json__(self) -> dict: ...


class CombinedTextNode(CombinedBaseNode):
	"""Text node in the combined tree."""

	text: str = Field(description='Text content')
	type: str = Field(default='TEXT_NODE', description='Node type identifier')

	def __json__(self) -> dict:
		return {
			'type': self.type,
			'text': self.text,
			'node_id': self.node_id,
			'backend_node_id': self.backend_node_id,
			'is_visible': self.is_visible,
			'has_accessibility': self.has_accessibility_data(),
			'accessibility_role': self.get_accessibility_role(),
			'accessibility_name': self.get_accessibility_name(),
		}

	def __repr__(self) -> str:
		extras = []
		if self.has_accessibility_data():
			role = self.get_accessibility_role()
			if role:
				extras.append(f'a11y:{role}')
		if self.is_new:
			extras.append('new')

		extra_str = f' [{", ".join(extras)}]' if extras else ''
		return f'Text: "{self.text}"{extra_str}'


class CombinedElementNode(CombinedBaseNode):
	"""Element node in the combined tree with DOM and accessibility data."""

	tag_name: str = Field(description='HTML tag name')
	attributes: dict[str, str] = Field(default_factory=dict, description='DOM attributes')

	# Interaction properties
	# is_interactive: bool = Field(default=False, description='Whether element is interactive')
	interactive_index: int | None = Field(None, description='Index of interactive element')

	# is_top_element: bool = Field(default=False, description='Whether element is top-level')
	is_in_viewport: bool = Field(default=False, description='Whether element is in viewport')

	# Layout properties
	shadow_root: bool = Field(default=False, description='Whether element has shadow root')
	xpath: str | None = Field(None, description='XPath to element')

	def __json__(self) -> dict:
		return {
			'tag_name': self.tag_name,
			'attributes': self.attributes,
			'node_id': self.node_id,
			'backend_node_id': self.backend_node_id,
			'is_visible': self.is_visible,
			'interactive_index': self.interactive_index,
			'is_in_viewport': self.is_in_viewport,
			'shadow_root': self.shadow_root,
			'xpath': self.xpath,
			'has_accessibility': self.has_accessibility_data(),
			'accessibility_role': self.get_accessibility_role(),
			'accessibility_name': self.get_accessibility_name(),
			'accessibility_description': self.get_accessibility_description(),
			'children': [child.__json__() for child in self.children],
		}

	def __repr__(self) -> str:
		tag_str = f'<{self.tag_name}'

		# Add key attributes
		key_attrs = ['id', 'class', 'type', 'role']
		for attr in key_attrs:
			if attr in self.attributes:
				tag_str += f' {attr}="{self.attributes[attr]}"'
		tag_str += '>'

		# Add extra info
		extras = []
		if self.interactive_index is not None:
			extras.append(f'interactive:{self.interactive_index}')
		if self.shadow_root:
			extras.append('shadow-root')
		if self.is_in_viewport:
			extras.append('in-viewport')
		if self.has_accessibility_data():
			role = self.get_accessibility_role()
			if role:
				extras.append(f'a11y:{role}')
		if self.is_new:
			extras.append('new')

		if extras:
			tag_str += f' [{", ".join(extras)}]'

		return tag_str

	def get_all_text_till_next_accessible_element(self, max_depth: int = -1) -> str:
		"""Get all text content until hitting another element with accessibility data."""
		text_parts = []

		def collect_text(node: CombinedBaseNode, current_depth: int) -> None:
			if max_depth != -1 and current_depth > max_depth:
				return

			# Skip this branch if we hit an accessible element (except for the current node)
			if isinstance(node, CombinedElementNode) and node != self and node.has_accessibility_data():
				return

			if isinstance(node, CombinedTextNode):
				text_parts.append(node.text)
			elif isinstance(node, CombinedElementNode):
				for child in node.children:
					collect_text(child, current_depth + 1)

		collect_text(self, 0)
		return '\n'.join(text_parts).strip()

	def accessible_elements_to_string(self, include_attributes: list[str] | None = None) -> str:
		"""Convert the processed DOM content to HTML, focusing on accessible elements."""
		from browser_use.dom.a11y.dom_tree_serializer import DOMTreeSerializer

		serializer = DOMTreeSerializer()
		return serializer.serialize_accessible_elements(self, include_attributes)


class CombinedTreeResponse(BaseModel):
	"""Response containing the combined DOM + accessibility tree."""

	root: CombinedBaseNode = Field(description='Root node of the combined tree')
	total_nodes: int = Field(description='Total number of nodes in the tree')
	accessible_nodes: int = Field(description='Number of nodes with accessibility data')
	interactive_nodes: int = Field(description='Number of interactive nodes')
	metadata: dict[str, Any] = Field(default_factory=dict, description='Additional metadata about the tree')


# Enable forward references
DOMNode.model_rebuild()
AXValue.model_rebuild()
AXValueSource.model_rebuild()
CombinedBaseNode.model_rebuild()
CombinedTextNode.model_rebuild()
CombinedElementNode.model_rebuild()
