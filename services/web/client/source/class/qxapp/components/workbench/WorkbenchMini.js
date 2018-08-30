/* eslint no-warning-comments: "off" */

const miniFactor = 3;

qx.Class.define("qxapp.components.workbench.WorkbenchMini", {
  extend: qx.ui.container.Composite,

  construct: function(workbenchData) {
    this.base();

    let canvas = new qx.ui.layout.Canvas();
    this.set({
      layout: canvas
    });

    this.__desktop = new qx.ui.window.Desktop(new qx.ui.window.Manager());
    this.add(this.__desktop, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__svgWidget = new qxapp.components.workbench.SvgWidget("SvgWidgetLayerMini");
    // this gets fired once the widget has appeared and the library has been loaded
    // due to the qx rendering, this will always happen after setup, so we are
    // sure to catch this event
    if (workbenchData) {
      this.__svgWidget.addListenerOnce("SvgWidgetReady", () => {
        // Will be called only the first time Svg lib is loaded
        this.loadProject(workbenchData);
      });
    }
    this.__desktop.add(this.__svgWidget, {
      left: 0,
      top: 0,
      right: 0,
      bottom: 0
    });

    this.__nodes = [];
    this.__links = [];
  },

  events: {
    "NodeDoubleClicked": "qx.event.type.Data"
  },

  members: {
    __nodes: null,
    __links: null,
    __desktop: null,
    __svgWidget: null,

    loadProject: function(workbenchData) {
      this.removeAll();

      for (let nodeUuid in workbenchData) {
        let nodeData = workbenchData[nodeUuid];
        const nodeImageId = nodeData.key + "-" + nodeData.version;
        let node = this.__createNode(nodeImageId, nodeUuid, nodeData);
        this.__addNodeToWorkbench(node, nodeData.position);
      }
      for (let nodeUuid in workbenchData) {
        let nodeData = workbenchData[nodeUuid];
        if (nodeData.inputs) {
          for (let prop in nodeData.inputs) {
            let link = nodeData.inputs[prop];
            if (typeof link == "object" && link.nodeUuid) {
              this.__addLink({
                nodeUuid: link.nodeUuid,
                output: link.output
              }, {
                nodeUuid: nodeUuid,
                input: prop
              });
            }
          }
        }
      }
    },

    __createNode: function(nodeImageId, uuid, nodeData) {
      let node = new qxapp.components.workbench.NodeBaseMini(nodeImageId, uuid);
      node.createNodeLayout();
      return node;
    },

    __addLink: function(from, to, linkId) {
      let node1Id = from.nodeUuid;
      let port1Id = "outPort";
      let node2Id = to.nodeUuid;
      let port2Id = "inPort";

      let node1 = this.getNode(node1Id);
      let port1 = node1.getOutputPort(port1Id);
      let node2 = this.getNode(node2Id);
      let port2 = node2.getInputPort(port2Id);

      const pointList = this.__getLinkPoints(node1, port1, node2, port2);
      const x1 = pointList[0][0];
      const y1 = pointList[0][1];
      const x2 = pointList[1][0];
      const y2 = pointList[1][1];
      let linkRepresentation = this.__svgWidget.drawCurveMini(x1, y1, x2, y2);
      let linkBase = new qxapp.components.workbench.LinkBase(linkRepresentation);
      linkBase.setInputNodeId(node1.getNodeId());
      linkBase.setInputPortId(port1.portId);
      linkBase.setOutputNodeId(node2.getNodeId());
      linkBase.setOutputPortId(port2.portId);
      if (linkId !== undefined) {
        linkBase.setLinkId(linkId);
      }
      this.__links.push(linkBase);

      return linkBase;
    },

    __removeNode: function(node) {
      this.__desktop.remove(node);
      let index = this.__nodes.indexOf(node);
      if (index > -1) {
        this.__nodes.splice(index, 1);
      }
    },

    __removeAllNodes: function() {
      while (this.__nodes.length > 0) {
        this.__removeNode(this.__nodes[this.__nodes.length-1]);
      }
    },

    __removeLink: function(link) {
      this.__svgWidget.removeCurve(link.getRepresentation());
      let index = this.__links.indexOf(link);
      if (index > -1) {
        this.__links.splice(index, 1);
      }
    },

    __removeAllLinks: function() {
      while (this.__links.length > 0) {
        this.__removeLink(this.__links[this.__links.length-1]);
      }
    },

    removeAll: function() {
      this.__removeAllNodes();
      this.__removeAllLinks();
    },

    __addNodeToWorkbench: function(node, position) {
      if (position === undefined || position === null) {
        let farthestRight = 0;
        for (let i=0; i < this.__nodes.length; i++) {
          let boundPos = this.__nodes[i].getBounds();
          let rightPos = boundPos.left + boundPos.width;
          if (farthestRight < rightPos) {
            farthestRight = rightPos;
          }
        }
        node.moveTo(parseInt((50 + farthestRight) / miniFactor), parseInt(200 / miniFactor));
        this.addWindowToDesktop(node);
        this.__nodes.push(node);
      } else {
        node.moveTo(parseInt(position.x/miniFactor), parseInt(position.y/miniFactor));
        this.addWindowToDesktop(node);
        this.__nodes.push(node);
      }

      node.addListener("appear", function() {
        this.__updateLinks(node);
      }, this);

      node.addListener("dblclick", function(e) {
        this.fireDataEvent("NodeDoubleClicked", node.getNodeId());
        e.stopPropagation();
      }, this);

      qx.ui.core.queue.Layout.flush();
    },

    nodeMoved: function(e) {
      const data = e.getData();
      let node = this.getNode(data.nodeId);
      if (node) {
        node.moveTo(parseInt(data.posX/miniFactor), parseInt(data.posY/miniFactor));
        this.__updateLinks(node);
      }
    },

    __updateLinks: function(node) {
      let linksInvolved = this.__getConnectedLinks(node.getNodeId());

      linksInvolved.forEach(linkId => {
        let link = this.__getLink(linkId);
        if (link) {
          let port1Id = "outPort";
          let port2Id = "inPort";
          let node1 = this.getNode(link.getInputNodeId());
          let port1 = node1.getOutputPort(port1Id);
          let node2 = this.getNode(link.getOutputNodeId());
          let port2 = node2.getInputPort(port2Id);
          const pointList = this.__getLinkPoints(node1, port1, node2, port2);
          const x1 = pointList[0][0];
          const y1 = pointList[0][1];
          const x2 = pointList[1][0];
          const y2 = pointList[1][1];
          this.__svgWidget.updateCurve(link.getRepresentation(), x1, y1, x2, y2);
        }
      });
    },

    __getLinkPoints: function(node1, port1, node2, port2) {
      let p1 = null;
      let p2 = null;
      // swap node-ports to have node1 as input and node2 as output
      if (port1.isInput) {
        [node1, port1, node2, port2] = [node2, port2, node1, port1];
      }
      p1 = node1.getLinkPoint(port1);
      p2 = node2.getLinkPoint(port2);
      // hack to place the arrow-head properly
      p2[0] -= 6;
      return [p1, p2];
    },

    getNode: function(id) {
      for (let i = 0; i < this.__nodes.length; i++) {
        if (this.__nodes[i].getNodeId() === id) {
          return this.__nodes[i];
        }
      }
      return null;
    },

    __getConnectedLinks: function(nodeId) {
      let connectedLinks = [];
      for (let i = 0; i < this.__links.length; i++) {
        if (this.__links[i].getInputNodeId() === nodeId) {
          connectedLinks.push(this.__links[i].getLinkId());
        }
        if (this.__links[i].getOutputNodeId() === nodeId) {
          connectedLinks.push(this.__links[i].getLinkId());
        }
      }
      return connectedLinks;
    },

    __getLink: function(id) {
      for (let i = 0; i < this.__links.length; i++) {
        if (this.__links[i].getLinkId() === id) {
          return this.__links[i];
        }
      }
      return null;
    },

    addWindowToDesktop: function(node) {
      this.__desktop.add(node);
      node.open();
    }
  }
});
