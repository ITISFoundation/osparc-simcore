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

    attachShowHideHandlers: function() {
      if (this.getElement()) {
        const element = this.getElement();

        const showHint = () => this.show();
        const hideHint = () => this.exclude();
        const tapListener = e => {
          // Make hint "modal" when parent element is clicked
          if (osparc.utils.Utils.isMouseOnElement(this, e)) {
            return;
          }
          hideHint();
          document.removeEventListener("mousedown", tapListener);
          element.addListener("mouseover", showHint);
          element.addListener("mouseout", hideHint);
        };

        element.addListener("mouseover", showHint);
        element.addListener("mouseout", hideHint);
        element.addListener("tap", () => {
          showHint();
          document.addEventListener("mousedown", tapListener);
          element.removeListener("mouseover", showHint);
          element.removeListener("mouseout", hideHint);
        }, this);
      }
    },

    getLabel: function() {
      return this.getChildControl("label");
    },

    getText: function() {
      return this.getChildControl("label").getValue();
    },

    setText: function(text) {
      this.getChildControl("label").setValue(text);
      setTimeout(() => this.updatePosition(), 10);
    }
  }
});
