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
 * Class that stores Link data.
 *
 *                                    -> {NODES}
 * STUDY -> METADATA + WORKBENCH ->|
 *                                    -> {LINKS}
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let link = new qxapp.data.model.Link(linkId, node1Id, node2Id);
 * </pre>
 */

qx.Class.define("qxapp.data.model.Link", {
  extend: qx.core.Object,

  /**
    * @param linkId {String} uuid if the link. If not provided, a random one will be assigned
    * @param node1Id {String} uuid of the node where the link comes from
    * @param node2Id {String} uuid of the node where the link goes to
  */
  construct: function(linkId, node1Id, node2Id) {
    this.base();

    this.setLinkId(linkId || qxapp.utils.Utils.uuidv4());
    this.setInputNodeId(node1Id);
    this.setOutputNodeId(node2Id);
  },

  properties: {
    linkId: {
      check: "String",
      nullable: false
    },

    inputNodeId: {
      init: null,
      check: "String"
    },

    outputNodeId: {
      init: null,
      check: "String"
    }
  }
});
