/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.user.UserExtras", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));
  },

  properties: {
    extras: {
      check: "Object",
      init: null,
      nullable: true,
      event: "changeExtras",
      apply: "__applyExtras",
    }
  },

  members: {
    __applyExtras: function(extras) {
      if (!extras) {
        return;
      }

      for (const key in extras) {
        const value = extras[key];
        if (osparc.utils.Utils.isDateLike(value)) {
          extras[key] = osparc.utils.Utils.formatDateAndTime(new Date(value));
        }
      }

      const jsonViewer = new osparc.widget.JsonFormatterWidget(extras);
      const scroll = new qx.ui.container.Scroll();
      scroll.add(jsonViewer);
      this._add(scroll, {
        flex: 1
      });
    },
  }
});
