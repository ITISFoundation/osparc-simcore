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
 * VirtualTreeItem used mainly by InputMapper
 *
 *   It consists of an entry icon and label
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new osparc.component.widget.InputsMapperTreeItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindDefaultProperties(item, id);
 *       c.bindProperty("isDir", "isDir", null, item, id);
 *       c.bindProperty("isRoot", "isRoot", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("osparc.component.widget.InputsMapperTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  properties: {
    isDir: {
      check: "Boolean",
      nullable: false,
      init: true
    },

    isRoot: {
      check: "Boolean",
      nullable: false,
      init: false
    },

    nodeKey: {
      check: "String",
      nullable: false
    },

    portKey: {
      check: "String",
      nullable: false
    }
  }
});
