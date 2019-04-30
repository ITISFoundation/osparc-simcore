/* ************************************************************************

   qxapp - the simcore frontend

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
 *   let link = new qxapp.data.model.Edge(linkId, node1Id, node2Id);
 *   let linkRepresentation = svgWidget.drawCurve(x1, y1, x2, y2);
 *   let linkUI = new qxapp.component.workbench.EdgeUI(link, linkRepresentation);
 * </pre>
 */

qx.Class.define("qxapp.component.workbench.EdgeUI", {
  extend: qx.core.Object,
  include: qxapp.component.filter.MFilterable,
  implement: qxapp.component.filter.IFilterable,

  /**
    * @param link {qxapp.data.model.Edge} Edge owning the object
    * @param representation {SVG Object} UI representation of the link
  */
  construct: function(edge, representation) {
    this.base();

    this.setEdge(edge);
    this.setRepresentation(representation);

    this._subscribeToFilterGroup("workbench");
  },

  events: {
    "linkSelected": "qx.event.type.Data"
  },

  properties: {
    edge: {
      check: "qxapp.data.model.Edge",
      nullable: false
    },

    representation: {
      init: null
    }
  },

  members: {
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
