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

qx.Class.define("osparc.ui.form.renderer.SingleWithWidget", {
  extend: qx.ui.form.renderer.Single,

  construct: function(form, widgets) {
    if (widgets) {
      this.__widgets = widgets;
    } else {
      this.__widgets = {};
    }

    this.base(arguments, form);
  },

  members: {
    __widgets: null,

    setWidgets: function(widgets) {
      this.__widgets = widgets;

      this._onFormChange();
    },

    // overridden
    _onFormChange: function() {
      // qx.ui.form.renderer.AbstractRenderer._onFormChange disposes and resets
      // this._labels but leaves stale (disposed) label references in this._names.
      // On a locale change, _onChangeLocale would then call setValue() on those
      // disposed labels, whose content element is null, and crash. Resetting
      // _names here keeps only the labels created by the upcoming re-render.
      if (qx.core.Environment.get("qx.dynlocale")) {
        this._names = [];
      }
      this.base(arguments);
    },

    // overridden
    addItems: function(items, names, title, itemOptions, headerOptions) {
      this.base(arguments, items, names, title, itemOptions, headerOptions);

      // header
      let row = title === null ? 0 : 1;

      for (let i = 0; i < items.length; i++) {
        if (i in this.__widgets) {
          const widget = this.__widgets[i];
          this._add(widget, {
            row,
            column: 2,
          });
        }

        row++;
      }
    },
  }
});
