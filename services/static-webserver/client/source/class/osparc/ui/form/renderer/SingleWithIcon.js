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

qx.Class.define("osparc.ui.form.renderer.SingleWithIcon", {
  extend: qx.ui.form.renderer.Single,

  construct: function(form, icons) {
    if (icons) {
      this.__icons = icons;
    } else {
      this.__icons = {};
    }

    this.base(arguments, form);
  },

  members: {
    __icons: null,

    setIcons(icons) {
      this.__icons = icons;

      this._render();
    },

    // overridden
    addItems: function(items, names, title, itemOptions, headerOptions) {
      this.base(arguments, items, names, title, itemOptions, headerOptions);

      // header
      let row = title === null ? 0 : 1;

      for (let i = 0; i < items.length; i++) {
        if (i in this.__icons) {
          const image = new qx.ui.basic.Image(this.__icons[i]).set({
            alignY: "middle",
          });
          this._add(image, {
            row,
            column: 2,
          });
        }

        row++;
      }
    },
  }
});
