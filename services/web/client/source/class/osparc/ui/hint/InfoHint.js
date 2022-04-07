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
  extend: osparc.ui.basic.IconButton,

  /**
   * Info button with hint as tooltip
   *
   * @extends osparc.ui.basic.IconButton
   */
  construct: function(hint) {
    this.base(arguments, "@MaterialIcons/info_outline/14");

    this.bind("hintText", this, "visibility", {
      converter: hintText => (hintText && hintText !== "") ? "visible" : "excluded"
    });

    if (hint) {
      this.setHintText(hint);
    }
  },

  properties: {
    hintText: {
      check: "String",
      init: null,
      event: "changeHintText",
      apply: "__applyHintText"
    }
  },

  members: {
    __applyHintText: function(hintText) {
      if (hintText && hintText !== "") {
        const hint = new osparc.ui.hint.Hint(this, hintText).set({
          active: false
        });

        const showHint = () => hint.show();
        const hideHint = () => hint.exclude();

        // Make hint "modal" when info button is clicked
        const tapListener = event => {
          if (osparc.utils.Utils.isMouseOnElement(hint, event)) {
            return;
          }
          hideHint();
          document.removeEventListener("mousedown", tapListener);
          this.addListener("mouseover", showHint);
          this.addListener("mouseout", hideHint);
        };

        this.addListener("mouseover", showHint);
        this.addListener("mouseout", hideHint);
        this.addListener("tap", () => {
          showHint();
          document.addEventListener("mousedown", tapListener);
          this.removeListener("mouseover", showHint);
          this.removeListener("mouseout", hideHint);
        }, this);
      }
    }
  }
});
