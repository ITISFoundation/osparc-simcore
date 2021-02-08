/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.hint.InfoHint", {
  extend: qx.ui.core.Widget,

  /**
   * Info button with hint as tooltip
   *
   * @extends qx.ui.core.Widget
   */
  construct: function(hint) {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox().set({
      alignX: "center",
      alignY: "middle"
    });
    this._setLayout(layout);

    const infoBtn = this._createChildControl("infobutton");
    this.bind("hintText", infoBtn, "visibility", {
      converter: hintText => hintText !== "" ? "visible" : "excluded"
    });

    if (hint) {
      this.setHintText(hint);
    }
  },

  properties: {
    hintText: {
      check: "String",
      init: "",
      apply: "__applyHintText"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "infobutton":
          control = new osparc.ui.basic.IconButton("@FontAwesome5Solid/info-circle/14");
          control.getContentElement().addClass("hint-button");
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyHintText: function(hintText) {
      if (hintText) {
        const infoBtn = this.getChildControl("infobutton");
        const hint = new osparc.ui.hint.Hint(infoBtn, hintText).set({
          active: false
        });

        const showHint = () => {
          hint.show();
        };
        const hideHint = () => {
          hint.exclude();
        };

        // Make hint "modal" when info button is clicked
        const tapListener = event => {
          const hintElement = hint.getContentElement().getDomElement();
          const boundRect = hintElement.getBoundingClientRect();
          if (event.x > boundRect.x &&
            event.y > boundRect.y &&
            event.x < (boundRect.x + boundRect.width) &&
            event.y < (boundRect.y + boundRect.height)) {
            return;
          }
          hideHint();
          document.removeEventListener("mousedown", tapListener);
          infoBtn.addListener("mouseover", showHint);
          infoBtn.addListener("mouseout", hideHint);
        };

        infoBtn.addListener("mouseover", showHint);
        infoBtn.addListener("mouseout", hideHint);
        infoBtn.addListener("tap", () => {
          showHint();
          document.addEventListener("mousedown", tapListener);
          infoBtn.removeListener("mouseover", showHint);
          infoBtn.removeListener("mouseout", hideHint);
        }, this);
      }
    }
  }
});
