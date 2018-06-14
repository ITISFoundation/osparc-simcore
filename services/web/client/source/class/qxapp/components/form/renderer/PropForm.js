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
qx.Class.define("qxapp.components.form.renderer.PropForm", {
  extend : qx.ui.form.renderer.Single,
  /**
     * create a page for the View Tab with the given title
     *
     * @param vizWidget {Widget} visualization widget to embedd
     */
  construct: function(form) {
    this.base(arguments, form);
    let fl = this._getLayout();
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
      }

      // add the items
      for (let i = 0; i < items.length; i++) {
        let item = items[i];
        let label = this._createLabel(names[i], item);
        this._add(label, {
          row: this._row,
          column: 0
        });
        label.setBuddy(item);
        this._add(item, {
          row: this._row,
          column: 1
        });
        if (itemOptions !== null && itemOptions[i] !== null && itemOptions[i].exposable) {
          let exposeCtrl = new qx.ui.form.CheckBox().set({
            marginLeft: 20,
            marginRight: 20
          });
          this._add(exposeCtrl, {
            row: this._row,
            column: 2
          });
          exposeCtrl.addListener("changeValue", function(e) {
            item.setEnabled(!e.getData());
          }, this);
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
    },

    enableProp: function(key, enable) {
      if (this._form && this._form.getControl(key)) {
        this._form.getControl(key).setEnabled(enable);
      }
    }
  }
});
