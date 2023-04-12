/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.hint.Hint", {
  extend: osparc.ui.basic.FloatingHelper,

  construct: function(element, text) {
    this.base(arguments, element);

    const label = this.getChildControl("label");
    this.add(label);
    if (text === undefined) {
      text = "";
    }
    label.setValue(text);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          control = new qx.ui.basic.Label().set({
            rich: true,
            maxWidth: 200
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    getLabel: function() {
      return this.getChildControl("label");
    },

    getText: function() {
      return this.getChildControl("label").getValue();
    },

    setText: function(text) {
      this.getChildControl("label").setValue(text);
    }
  }
});
