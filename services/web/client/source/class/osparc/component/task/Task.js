/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.task.Task", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox(10).set({
      alignY: "middle"
    });
    this._setLayout(layout);

    this.set({
      height: 30,
      backgroundColor: "material-button-background"
    });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon-status":
          control = new osparc.ui.form.FetchButton();
          this._add(control);
          break;
        case "label":
          control = new qx.ui.basic.Label().set({
            allowGrowX: false,
            maxWidth: 200
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "icon-stop":
          control = new qx.ui.basic.Image("@MaterialIcons/close/16").set({
            cursor: "pointer"
          });
          control.addListener("tap", () => {
            this._stopTask();
          }, this);
          break;
      }
      return control || this.base(arguments, id);
    },

    /**
      * @abstract
      */
    _stopTask: function() {
      throw new Error("Abstract method called!");
    }
  }
});
