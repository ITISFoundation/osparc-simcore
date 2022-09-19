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
 *   let edgeUI = new osparc.component.workbench.EdgeUI(edge, edgeRepresentation);
 * </pre>
 */

qx.Class.define("osparc.component.workbench.EdgeUI", {
  extend: qx.core.Object,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,

  /**
    * @param edge {osparc.data.model.Edge} Edge owning the object
    * @param representation {SVG Object} UI representation of the edge
  */
  construct: function(edge, representation) {
    this.base();

    this.setEdge(edge);
    this.setRepresentation(representation);

    if (edge.getInputNode()) {
      edge.getInputNode().getStatus().addListener("changeModified", () => {
        this.__updateEdgeColor();
      });
    }
    this.__updateEdgeColor();

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
    getEdgeColor(modified) {
      let newColor = null;
      if (modified === null) {
        newColor = qx.theme.manager.Color.getInstance().resolve("workbench-edge-comp-active");
      } else {
        newColor = osparc.utils.StatusUI.getColor(modified ? "failed" : "ready");
      }
      const colorHex = qx.theme.manager.Color.getInstance().resolve(newColor);
      return colorHex;
    }
  },

  members: {
    __updateEdgeColor: function() {
      let colorHex = this.self().getEdgeColor(false);
      if (this.getEdge().getInputNode()) {
        const modified = this.getEdge().getInputNode().getStatus()
          .getModified();
        colorHex = this.self().getEdgeColor(modified);
      }
      osparc.wrapper.Svg.updateCurveColor(this.getRepresentation(), colorHex);
    },

    setSelected: function(selected) {
      if (selected) {
        const selectedColor = qx.theme.manager.Color.getInstance().resolve("workbench-edge-selected");
        osparc.wrapper.Svg.updateCurveColor(this.getRepresentation(), selectedColor);
      } else {
        this.__updateEdgeColor();
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
