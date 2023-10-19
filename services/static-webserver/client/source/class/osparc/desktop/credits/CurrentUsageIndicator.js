/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Julian Querido (jsaq007)

************************************************************************ */

qx.Class.define("osparc.desktop.credits.CurrentUsageIndicator", {
  extend: qx.ui.core.Widget,

  construct: function(currentUsage) {
    this.base(arguments);

    this._createChildControlImpl("usage-label");

    if (currentUsage) {
      this.set({
        currentUsage
      });
    }
  },

  properties: {
    currentUsage: {
      check: "osparc.desktop.credits.CurrentUsage",
      init: null,
      nullable: false,
      apply: "__applyCurrentUsage"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "usage-label":
          control = new qx.ui.basic.Label().set({
            font: "text-16"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyCurrentUsage: function(currentUsage) {
      currentUsage.bind("currentUsage", this, "value", {
        converter: currentUsageValue => currentUsageValue + this.tr(" used")
      });
      currentUsage.bind("currentUsage", this, "visibility", {
        converter: currentUsageValue => currentUsageValue === null ? "excluded" : "visible"
      });
    }
  }
});
