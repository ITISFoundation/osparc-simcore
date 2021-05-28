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
 * ListItem used mainly by NodeOutputListIcon
 *
 *   It consists of an entry thumbnail and label.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   list.setDelegate({
 *     createItem: () => new osparc.component.widget.inputs.NodeOutputListIconItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindDefaultProperties(item, id);
 *       c.bindProperty("key", "model", null, item, id);
 *       c.bindProperty("thumbnail", "icon", null, item, id);
 *       c.bindProperty("label", "label", {
 *         converter: function(data) {
 *           return data;
 *         }
 *       }, item, id);
 *     },
 *   });
 * </pre>
 */

qx.Class.define("osparc.component.widget.inputs.NodeOutputListIconItem", {
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
