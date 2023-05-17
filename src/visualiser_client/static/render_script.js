const { shapes, util, dia, anchors } = joint;

// Visual settings for the visualizer
let settings_dict = {
    "common": {
        "backgroundColor": 'rgba(224, 233, 227, 0.3)',
        gridSize: 1,
        "pinLabelFontSize": 8,
        "pinLabelPadding": 5,
        "parentPadding": 50
    },
    "component" : {
        "strokeWidth": 2,
        "fontSize": 12,
        "defaultWidth": 40,
        portPitch: 20,
        "defaultHeight": 40,
    },
    "block" : {
        strokeWidth: 2,
        boxRadius: 5,
        strokeDasharray: '4,4',
        fontSize: 10,
    },
    "link": {
        "strokeWidth": 1,
        "color": "blue"
    }
}

// Base class for the visual elements
class AtoElement extends dia.Element {
    defaults() {
        return {
            ...super.defaults,
            hidden: false,
        };
    }

    isHidden() {
        return Boolean(this.get("hidden"));
    }

    static isAtoElement(shape) {
        return shape instanceof AtoElement;
    }
}

// Class for a component
class AtoComponent extends AtoElement {
    defaults() {
        return {
            ...super.defaults(),
            type: "AtoComponent",
            size: { width: settings_dict["component"]["defaultWidth"],
                    height: settings_dict["component"]["defaultHeight"] },
            attrs: {
                body: {
                    fill: "white",
                    z: 10,
                    stroke: "black",
                    strokeWidth: settings_dict["component"]["strokeWidth"],
                    width: "calc(w)",
                    height: "calc(h)",
                    rx: 5,
                    ry: 5
                },
                label: {
                    text: "Component",
                    fill: "black",
                    fontSize: settings_dict["component"]["fontSize"],
                    fontWeight: "bold",
                    textVerticalAnchor: "middle",
                    textAnchor: "middle",
                    fontFamily: "sans-serif",
                    x: "calc(w/2)",
                    y: "calc(h/2)"
                }
            }
        };
    }

    preinitialize() {
        this.markup = util.svg`
            <rect @selector="body" />
            <text @selector="label" />
        `;
    }

    fitAncestorElements() {
        var padding = settings_dict['common']['parentPadding'];
        this.fitParent({
            deep: true,
            padding: {
                top: padding,
                left: padding,
                right: padding,
                bottom: padding
            }
        });
    }
}

// Class for a block
// For the moment, blocks and components are separate.
// We might want to combine them in the future.
class AtoBlock extends dia.Element {
    defaults() {
      return {
        ...super.defaults,
        type: "AtoBlock",
        size: { width: 10, height: 10 },
        collapsed: false,
        attrs: {
          body: {
            fill: "transparent",
            stroke: "#333",
            strokeWidth: settings_dict["block"]["strokeWidth"],
            strokeDasharray: settings_dict["block"]["strokeDasharray"],
            width: "calc(w)",
            height: "calc(h)",
            rx: settings_dict["block"]["boxRadius"],
            ry: settings_dict["block"]["boxRadius"],
          },
          label: {
            text: "Block",
            fill: "#333",
            fontSize: settings_dict["block"]["strokeWidth"],
            fontWeight: "bold",
            textVerticalAnchor: "middle",
            textAnchor: "middle",
            fontFamily: "sans-serif",
            x: "calc(w / 2)"
          }
        }
      };
    }

    preinitialize(...args) {
      this.markup = util.svg`
              <rect @selector="body" />
              <text @selector="label" />
          `;
    }

    updateChildrenVisibility() {
      const collapsed = this.isCollapsed();
      this.getEmbeddedCells().forEach((child) => child.set("hidden", collapsed));
    }

    fitAncestorElements() {
        var padding = 10;
        this.fitParent({
            deep: true,
            padding: {
                top:  padding,
                left: padding,
                right: padding,
                bottom: padding
            }
        });
    }
  }


const cellNamespace = {
    ...shapes,
    AtoElement,
    AtoComponent,
    AtoBlock
};

function addPortsAndPins(element, port_list) {
    // Dict of all the port for the element
    let port_groups = {};

    let pin_nb_by_port = {};
    // Create the different ports
    for (let port of port_list) {

        pin_nb_by_port[port['location']] = 0;

        port_groups[port['name']] = {
            position: {
                name: port['location'],
            },
            attrs: {
                portBody: {
                    magnet: true,
                    r: 2,
                    fill: '#FFFFFF',
                    stroke:'#023047'
                }
            },
            label: {
                position: {
                    args: { x: 0 }, // Can't use inside/outside in combination
                    name: 'outside'
                },
                markup: [{
                    tagName: 'text',
                    selector: 'label',
                    className: 'label-text'
                }]
            },
            markup: [{
                tagName: 'circle',
                selector: 'portBody'
            }]
        };

        // While we are creating the port, add the pins in the element
        for (let pin of port['pins']) {
            pin_nb_by_port[port['location']] += 1;
            element.addPort({
                id: pin["uuid"],
                group: port['name'],
                attrs: {
                    label: {
                        text: pin['name'],
                        fontFamily: "sans-serif",
                        fontSize: settings_dict['common']['pinLabelFontSize'],
                    }
                }
            });
            pin_to_element_association[pin["uuid"]] = element["id"];
        }
    };

    let top_pin_number = 'top' in pin_nb_by_port ? pin_nb_by_port.top : undefined;
    let bottom_pin_number = 'bottom' in pin_nb_by_port ? pin_nb_by_port.bottom : undefined;
    let left_pin_number = 'left' in pin_nb_by_port ? pin_nb_by_port.left : undefined;
    let right_pin_number = 'right' in pin_nb_by_port ? pin_nb_by_port.right : undefined;

    let max_width = Math.max(top_pin_number || -Infinity, bottom_pin_number || -Infinity);
    let max_height = Math.max(left_pin_number || -Infinity, right_pin_number || -Infinity);

    let component_width = settings_dict['component']['defaultWidth'];
    if (max_width > 0) {
        component_width += settings_dict['component']['portPitch'] * max_width;
    }
    let component_height = settings_dict['component']['defaultHeight'];
    if (max_height > 0) {
        component_height += settings_dict['component']['portPitch'] * max_height;
    }
    console.log('max width ', component_width, ' max height ', component_height);
    element.resize(component_width, component_height);

    // Add the ports list to the element
    element.prop({"ports": { "groups": port_groups}});
}

function addLinks(links) {
    for (let link of links) {
        var added_link = new shapes.standard.Link({
            source: {
                id: pin_to_element_association[link['source']],
                port: link['source']
            },
            target: {
                id: pin_to_element_association[link['target']],
                port: link['target']
            }
        });
        added_link.attr({
            line: {
                'stroke': settings_dict['link']['color'],
                'stroke-width': settings_dict['link']['strokeWidth'],
                targetMarker: {'type': 'none'}
            },
            z: 0
          });
        added_link.addTo(graph);

        var verticesTool = new joint.linkTools.Vertices();
        var segmentsTool = new joint.linkTools.Segments();
        var boundaryTool = new joint.linkTools.Boundary();

        var toolsView = new joint.dia.ToolsView({
            tools: [verticesTool, boundaryTool]
        });

        var linkView = added_link.findView(paper);
        linkView.addTools(toolsView);
        linkView.showTools();

    }
}

function createComponent(title, uuid, ports_dict, x, y) {
    const component = new AtoComponent({
        id: uuid,
        attrs: {
            label: {
                text: title
            }
        }
    });

    addPortsAndPins(component, ports_dict);

    component.addTo(graph);
    component.position(x, y, { parentRelative: true });
    return component;
}

function createBlock(title, uuid, ports_dict, x, y) {
    const block = new AtoBlock({
        id: uuid,
        attrs: {
            label: {
                text: title
            }
        }
    });

    addPortsAndPins(block, ports_dict);

    block.addTo(graph);
    block.position(x, y, { parentRelative: false });
    return block;
}

function addElementToElement(block_to_add, to_block) {
    to_block.embed(block_to_add);
}

function visulatizationFromDict(element, is_root = true, parent = null) {
    // Create the list of all the created elements
    let dict_of_elements = {};

    if (element['type'] == 'component') {
        let created_comp = createComponent(title = element['name'], uuid = element['uuid'], element['ports'], x = 100, y = 100);
        dict_of_elements[element['uuid']] = created_comp;
        if (parent) {
            addElementToElement(created_comp, parent);
        }
        //console.log('dict of element' + JSON.stringify(dict_of_elements[element['uuid']]));
    }

    // If it is a block, create it
    else if (element['type'] == 'module') {
        let created_block = null
        console.log('made it')
        if (is_root == false) {
            console.log(element['name'])
            created_block = createBlock(title = element['name'], uuid = element['uuid'], element['ports'], 100, 100);
        }
        if (parent) {
            addElementToElement(created_block, parent);
        }
        dict_of_elements[element['uuid']] = created_block;
        // Itterate over the included elements to create them
        for (let nested_element of element['blocks']) {
            let returned_dict = visulatizationFromDict(nested_element, is_root = false, created_block);
            console.log('returned dict keys ' + Object.keys(returned_dict) );//+ ' from ' + nested_element)
            //addElementsToElement(returned_dict, created_block);
            // Add the returned list to the element list and add all sub-elements to it's parent
            dict_of_elements = { ...dict_of_elements, ...returned_dict };
        }

        addLinks(element['links']);
    }

    return dict_of_elements;
}

const graph = new dia.Graph({}, { cellNamespace });
const paper = new joint.dia.Paper({
    el: document.getElementById('atopilePaper'),
    model: graph,
    width: 1000,
    height: 600,
    gridSize: settings_dict['common']['gridSize'],
    drawGrid: true,
    background: {
        color: settings_dict["common"]["backgroundColor"]
    },
    defaultRouter: {name: 'manhattan'},
    interactive: true,
    cellViewNamespace: cellNamespace,
});

let pin_to_element_association = {};
let element_dict = {};

paper.on('link:mouseenter', function(linkView) {
    linkView.showTools();
    linkView.highlight();
});

paper.on('link:mouseleave', function(linkView) {
    linkView.hideTools();
    linkView.unhighlight();
});

paper.on('cell:pointerup', function(evt, x, y) {
    const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(graph.toJSON()) // << data going the other way
    };
    fetch('/api/graph', requestOptions);
});

paper.on('element:pointermove', function(elementView) {
    var element = elementView.model;
    // `fitAncestorElements()` method is defined at `joint.shapes.container.Base` in `./joint.shapes.container.js`
    element.fitAncestorElements();
});

async function loadData() {
    const response = await fetch('/api/graph');
    const vis_dict = await response.json();

    console.log(vis_dict);
    element_dict = visulatizationFromDict(vis_dict);
}

loadData();
