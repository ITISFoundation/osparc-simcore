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

/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "allow": ["__ctrlMap"] }] */

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

  events: {
    "PortDragOver": "qx.event.type.Data",
    "PortDrop": "qx.event.type.Data"
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
        if (item.isLinked) {
          let unlinkBtn = new qx.ui.form.Button().set({
            icon: "@FontAwesome5Solid/unlink/16"
          });
          this._add(unlinkBtn, {
            row: this._row,
            column: 2
          });
          unlinkBtn.addListener("execute", function() {
            console.log("Unlink", item.key);
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
        label.setDroppable(true);
        item.setDroppable(true);
        this.__createUIPortConnections(label, item.key);
        this.__createUIPortConnections(item, item.key);
      }
    },

    getValues: function() {
      return this._form.getData();
    },

    enableProp: function(key, enable) {
      if (this._form && this._form.getControl(key)) {
        this._form.getControl(key).setEnabled(enable);
      }
    },

    enableAllProps: function(enable) {
      for (const key in this._form.__ctrlMap) {
        this.enableProp(key, enable);
      }
    },

    __createUIPortConnections: function(uiElement, portId) {
      [
        ["dragover", "PortDragOver"],
        ["drop", "PortDrop"]
      ].forEach(eventPair => {
        uiElement.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            // nodeId: nodeId,
            portId: portId
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    }
  }
});
