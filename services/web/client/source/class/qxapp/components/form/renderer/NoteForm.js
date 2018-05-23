/* ************************************************************************
   Copyright: 2013 OETIKER+PARTNER AG
              2018 ITIS Foundation
   License:   MIT
   Authors:   Tobi Oetiker <tobi@oetiker.ch>
   Utf8Check: äöü
************************************************************************ */

/**
 * A special renderer for AutoForms which includes notes below the section header
 * widget and next to the individual form widgets.
 */
qx.Class.define("qxapp.components.form.renderer.NoteForm", {
  extend : qx.ui.form.renderer.Single,
  /**
     * create a page for the View Tab with the given title
     *
     * @param vizWidget {Widget} visualization widget to embedd
     */
  construct: function(form) {
    this.base(arguments, form);
    var fl = this._getLayout();
    // have plenty of space for input, not for the labels
    fl.setColumnFlex(0, 0);
    fl.setColumnAlign(0, "left", "top");
    fl.setColumnFlex(1, 1);
    fl.setColumnMinWidth(1, 130);
  },

  members: {
    addItems: function(items, names, title, itemOptions, headerOptions) {
      // add the header
      if (title !== null) {
        this._add(
          this._createHeader(title), {
            row: this._row,
            column: 0,
            colSpan: 3
          }
        );
        this._row++;
        if (headerOptions !== null && headerOptions.note !== null) {
          this._add(new qx.ui.basic.Label(headerOptions.note).set({
            rich: true,
            alignX: "left"
          }), {
            row: this._row,
            column: 0,
            colSpan: 3
          });
          this._row++;
        }
      }

      // add the items
      for (var i = 0; i < items.length; i++) {
        var label = this._createLabel(names[i], items[i]);
        this._add(label, {
          row: this._row,
          column: 0
        });
        var item = items[i];
        label.setBuddy(item);
        this._add(item, {
          row: this._row,
          column: 1
        });
        if (itemOptions !== null && itemOptions[i] !== null && itemOptions[i].note) {
          this._add(new qx.ui.basic.Label(itemOptions[i].note).set({
            rich: true,
            marginLeft: 20,
            marginRight: 20
          }), {
            row: this._row,
            column: 2
          });
        }
        this._row++;
        this._connectVisibility(item, label);
        // store the names for translation
        if (qx.core.Environment.get("qx.dynlocale")) {
          this._names.push({
            name: names[i],
            label: label,
            item: items[i]
          });
        }
      }
    }
  }
});
