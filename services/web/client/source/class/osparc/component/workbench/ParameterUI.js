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

qx.Class.define("osparc.component.workbench.ParameterUI", {
  extend: osparc.component.workbench.BaseNodeUI,

  /**
    * @param parameter
    */
  construct: function(parameter) {
    this.base(arguments);

    this.set({
      width: this.self().NODE_WIDTH,
      maxWidth: this.self().NODE_WIDTH,
      minWidth: this.self().NODE_WIDTH
    });

    this.__parameter = parameter;

    this._createWindowLayout();
  },

  statics: {
    NODE_WIDTH: 80,
    NODE_HEIGHT: 80,
    CIRCLED_RADIUS: 32
  },

  members: {
    __parameter: null,

    getNodeType: function() {
      return "parameter";
    },

    getParameter: function() {
      return this.__parameter;
    },

    getParameterId: function() {
      if ("id" in this.__parameter) {
        return this.__parameter["id"];
      }
      return null;
    },

    // overridden
    _createWindowLayout: function() {
      this.__inputOutputLayout = this.getChildControl("inputOutput");
    },

    populateParameterLayout: function() {
      this.setCaption(this.__parameter["label"]);

      const isInput = false;
      this._createUIPorts(isInput);

      this._turnIntoCircledUI(this.self().NODE_WIDTH, this.self().CIRCLED_RADIUS);
      this._populateLayout();
    },

    _populateLayout: function() {
      const value = this.__parameter["low"];
      const label = new qx.ui.basic.Label(String(value)).set({
        font: "text-24",
        allowGrowX: true,
        textAlign: "center",
        padding: 6
      });
      this.__inputOutputLayout.addAt(label, 1, {
        flex: 1
      });
    },

    // overridden
    _createUIPorts: function() {
      const isInput = false;

      const portLabel = this.__createUIPortLabel(isInput);
      const label = {
        isInput: isInput,
        ui: portLabel
      };
      portLabel.setTextColor(osparc.utils.StatusUI.getColor("ready"));
      label.ui.isInput = false;
      this._addDragDropMechanism(label.ui, isInput);

      this.__outputLayout = label;
      const nElements = this.__inputOutputLayout.getChildren().length;
      this.__inputOutputLayout.addAt(label.ui, nElements, {
        flex: 1
      });
    }
  }
});
