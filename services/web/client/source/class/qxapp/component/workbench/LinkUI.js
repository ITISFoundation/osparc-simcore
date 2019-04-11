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
 * Object that owns the Link data model and it's representation
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let link = new qxapp.data.model.Link(linkId, node1Id, node2Id);
 *   let linkRepresentation = svgWidget.drawCurve(x1, y1, x2, y2);
 *   let linkUI = new qxapp.component.workbench.LinkUI(link, linkRepresentation);
 * </pre>
 */

qx.Class.define("qxapp.component.workbench.LinkUI", {
  extend: qx.core.Object,
  include: qxapp.component.filter.MFilterable,
  implement: qxapp.component.filter.IFilterable,

  /**
    * @param link {qxapp.data.model.Link} Link owning the object
    * @param representation {SVG Object} UI representation of the link
  */
  construct: function(link, representation) {
    this.base();

    this.setLink(link);
    this.setRepresentation(representation);

    this._subscribeToFilterGroup("workbench");
  },

  events: {
    "linkSelected": "qx.event.type.Data"
  },

  properties: {
    link: {
      check: "qxapp.data.model.Link",
      nullable: false
    },

    representation: {
      init: null
    }
  },

  members: {
    getLinkId: function() {
      return this.getLink().getLinkId();
    },

    _filter: function() {
      this.getRepresentation().node.style.opacity = 0.15;
    },

    _unfilter: function() {
      this.getRepresentation().node.style.opacity = 1;
    },

    _shouldFilterOut: function(data) {
      return true;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      return false;
    }
  }
});
