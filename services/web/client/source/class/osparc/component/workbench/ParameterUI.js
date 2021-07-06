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

    this.setParameter(parameter);

    this._createWindowLayout();
  },

  properties: {
    parameter: {
      check: "Object",
      nullable: false,
      init: null
    }
  },

  statics: {
    NODE_WIDTH: 80,
    NODE_HEIGHT: 80,
    CIRCLED_RADIUS: 32
  },

  members: {
    getNodeType: function() {
      return "parameter";
    },

    getParameterId: function() {
      if (this.getParameter()) {
        return this.getParameter()["id"];
      }
      return null;
    },

    // overridden
    _createWindowLayout: function() {
      this._inputOutputLayout = this.getChildControl("input-output");
    },

    populateParameterLayout: function() {
      this.setCaption(this.getParameter()["label"]);

      const isInput = false;
      this._createUIPorts(isInput);

      this._turnIntoCircledUI(this.self().NODE_WIDTH, this.self().CIRCLED_RADIUS);
      this._populateLayout();
    },

    _populateLayout: function() {
      const value = this.getParameter()["low"];
      const label = new qx.ui.basic.Label(String(value)).set({
        font: "text-24",
        allowGrowX: true,
        textAlign: "center",
        padding: 6
      });
      this._inputOutputLayout.addAt(label, 1, {
        flex: 1
      });
    },

    // overridden
    _createUIPorts: function() {
      const isInput = false;

      const portLabel = this._createUIPortLabel(isInput);
      const label = {
        isInput: isInput,
        ui: portLabel
      };
      portLabel.setTextColor(osparc.utils.StatusUI.getColor("ready"));
      label.ui.isInput = false;
      this._addDragDropMechanism(label.ui, isInput);

      this._outputLayout = label;
      const nElements = this._inputOutputLayout.getChildren().length;
      this._inputOutputLayout.addAt(label.ui, nElements, {
        flex: 1
      });
    },

    // overridden
    _createDragDropEventData: function(e, isInput) {
      return {
        event: e,
        parameterId: this.getParameterId(),
        isInput: isInput
      };
    },

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }

      const coords = this._setPositionFromEvent(e);
      this.getParameter()["xPos"] = coords.x;
      this.getParameter()["yPos"] = coords.y;

      this.base(arguments, e);
    },

    // implement osparc.component.filter.IFilterable
    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.getParameter()["label"]
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      return false;
    }
  }
});
