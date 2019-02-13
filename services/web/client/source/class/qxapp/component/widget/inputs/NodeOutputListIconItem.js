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
 * VirtualTreeItem used mainly by NodeOutputTreeItem
 *
 *   It consists of an entry icon and label and contains more information like: isDir,
 * isRoot, nodeKey, portKey, key
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new qxapp.component.widget.inputs.NodeOutputTreeItem(),
 *     bindItem: (c, item, id) => {
 *      c.bindDefaultProperties(item, id);
 *     },
 *     configureItem: item => {
 *       item.set({
 *       isDir: !portKey.includes("modeler") && !portKey.includes("sensorSettingAPI") && !portKey.includes("neuronsSetting"),
 *       nodeKey: node.getKey(),
 *       portKey: portKey
 *     });
 *   });
 * </pre>
 */

qx.Class.define("qxapp.component.widget.inputs.NodeOutputListIconItem", {
  extend: qx.ui.form.ListItem,

  construct: function() {
    this.base(arguments);

    let layout = new qx.ui.layout.VBox().set({
      alignY: "middle"
    });
    this._setLayout(layout);
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new qx.ui.basic.Image(this.getIcon()).set({
            alignX: "center"
          });
          this._add(control);
          break;
        case "label":
          control = new qx.ui.basic.Label(this.getLabel()).set({
            alignX: "center",
            rich: true,
            allowGrowY: false
          });
          this._add(new qx.ui.core.Spacer(1, 5));
          this._add(control);
          this._add(new qx.ui.core.Spacer(1, 15));
          break;
      }

      return control || this.base(arguments, id);
    }
  }
});
