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
    this.base(arguments, this.self().INFO_ICON);

    this.__createHint();

    this.bind("hintText", this, "visibility", {
      converter: hintText => (hintText && hintText !== "") ? "visible" : "excluded"
    });

    if (hint) {
      this.setHintText(hint);
    }
  },

  statics: {
    INFO_ICON: "@MaterialIcons/info_outline/14"
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
    _hint: null,

    __createHint: function() {
      const hint = this._hint = new osparc.ui.hint.Hint(this).set({
        active: false
      });
      this.addListenerOnce("appear", () => hint.attachShowHideHandlers());
    },

    __applyHintText: function(hintText) {
      this._hint.setText(hintText);
    }
  }
});
