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

    const layout = new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    });
    this._setLayout(layout);

    this.set({
      height: 30,
      maxWidth: 250,
      backgroundColor: "material-button-background"
    });
  },

  properties: {
    title: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeTitle"
    },

    subtitle: {
      check: "String",
      init: "",
      nullable: true,
      event: "changeSubtitle"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon":
          control = new osparc.ui.form.FetchButton().set({
            width: 25
          });
          this._add(control);
          break;
        case "title":
          control = new qx.ui.basic.Label();
          this.bind("title", control, "value");
          this._add(control);
          break;
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            allowGrowX: true
          });
          this.bind("subtitle", control, "value");
          this._add(control, {
            flex: 1
          });
          break;
        case "stop":
          control = new qx.ui.basic.Image("@MaterialIcons/close/16").set({
            alignY: "middle",
            alignX: "center",
            width: 25,
            cursor: "pointer"
          });
          control.addListener("tap", () => {
            this._stopTask();
          }, this);
          this._add(control);
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
