/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.node.StartStopButton", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this._createChildControlImpl("start-button");
    this._createChildControlImpl("stop-button");

    if (node) {
      this.setNode(node);
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      event: "changeNode",
      apply: "__applyNode"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "start-button":
          control = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/play/14",
            allowGrowX: false,
            enabled: false
          });
          control.addListener("execute", () => this.fireEvent("startPressed"));
          this._add(control);
          break;
        case "stop-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Stop"),
            icon: "@FontAwesome5Solid/stop/14",
            allowGrowX: false,
            enabled: false
          });
          control.addListener("execute", () => this.fireEvent("stopPressed"));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyNode: function(node) {
      if (node) {
        const startButton = this.getChildControl("start-button");
        const stopButton = this.getChildControl("stop-button");
        if (node.isDynamic()) {
          startButton.setLabel(this.tr("Start"));
          node.attachHandlersToStartButton(startButton);
          node.attachHandlersToStopButton(stopButton);
        } else {
          startButton.setLabel(this.tr("Run"));
        }
      }
    }
  }
});
