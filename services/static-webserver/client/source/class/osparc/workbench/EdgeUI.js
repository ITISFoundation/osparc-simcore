/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Object that owns the Edge data model and it's representation
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let edge = new osparc.data.model.Edge(edgeId, node1, node2);
 *   let edgeRepresentation = svgWidget.drawCurve(x1, y1, x2, y2);
 *   let edgeUI = new osparc.workbench.EdgeUI(edge, edgeRepresentation);
 * </pre>
 */

qx.Class.define("osparc.workbench.EdgeUI", {
  extend: qx.core.Object,
  include: osparc.filter.MFilterable,
  implement: osparc.filter.IFilterable,

  /**
    * @param edge {osparc.data.model.Edge} Edge owning the object
    * @param representation {SVG Object} UI representation of the edge
  */
  construct: function(edge, representation) {
    this.base();

    this.setEdge(edge);
    this.setRepresentation(representation);

    const hint = new osparc.ui.hint.Hint(null, "");
    representation.hint = hint;

    if (edge.getInputNode()) {
      edge.getInputNode().getStatus().addListener("changeModified", () => this.__updateEdgeState());
    }
    edge.addListener("changePortConnected", () => this.__updateEdgeState());

    this.__updateEdgeState();

    this.subscribeToFilterGroup("workbench");
  },

  properties: {
    edge: {
      check: "osparc.data.model.Edge",
      nullable: false
    },

    representation: {
      init: null
    }
  },

  statics: {
    getEdgeColor: function(modified) {
      let newColor = null;
      if (modified === null) {
        newColor = qx.theme.manager.Color.getInstance().resolve("workbench-edge-comp-active");
      } else {
        newColor = osparc.service.StatusUI.getColor(modified ? "failed" : "ready");
      }
      const colorHex = qx.theme.manager.Color.getInstance().resolve(newColor);
      return colorHex;
    },

    noPortsConnectedText: function(edge) {
      return `Connection candidate.<br>Check the ${edge.getOutputNode().getLabel()} inputs`;
    }
  },

  members: {
    __updateEdgeState: function() {
      const inputNode = this.getEdge().getInputNode();
      const portConnected = this.getEdge().isPortConnected();
      const modified = inputNode ? inputNode.getStatus().getModified() : false;

      // color
      const colorHex = this.self().getEdgeColor(modified);
      osparc.wrapper.Svg.updateCurveColor(this.getRepresentation(), colorHex);

      // shape
      osparc.wrapper.Svg.updateCurveDashes(this.getRepresentation(), !portConnected);

      // tooltip
      const hint = this.getHint();
      if (this.getEdge().isPortConnected() === false) {
        hint.setText(this.self().noPortsConnectedText(this.getEdge()));
      } else if (modified) {
        hint.setText("Out-of-date");
      } else {
        hint.setText(null);
      }
    },

    getHint: function() {
      return this.getRepresentation().hint;
    },

    setSelected: function(selected) {
      if (selected) {
        const selectedColor = qx.theme.manager.Color.getInstance().resolve("workbench-edge-selected");
        osparc.wrapper.Svg.updateCurveColor(this.getRepresentation(), selectedColor);
      } else {
        this.__updateEdgeState();
      }
    },

    setHighlighted: function(highlight) {
      if (highlight) {
        const strongColor = qx.theme.manager.Color.getInstance().resolve("strong-main");
        osparc.wrapper.Svg.updateCurveColor(this.getRepresentation(), strongColor);
      } else {
        this.__updateEdgeState();
      }
    },

    getEdgeId: function() {
      return this.getEdge().getEdgeId();
    },

    _filter: function() {
      this.getRepresentation().node.style.opacity = 0.15;
    },

    _unfilter: function() {
      this.getRepresentation().node.style.opacity = 1;
    },

    _shouldApplyFilter: function(data) {
      return data.text && data.text.length > 1 ||
        data.tags && data.tags.length;
    },

    _shouldReactToFilter: function(data) {
      return true;
    }
  }
});
