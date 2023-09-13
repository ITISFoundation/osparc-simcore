/* ************************************************************************
   Copyright: 2013 OETIKER+PARTNER AG
              2018 ITIS Foundation
   License:   MIT
   Authors:   Tobi Oetiker <tobi@oetiker.ch>
   Utf8Check: äöü
************************************************************************ */

/**
 * Create a form. The argument to the form
 * widget defines the structure of the form.
 *
 * <pre class='javascript'>
 *   {
 *     key: {
 *       displayOrder: 5,
 *       label: "Widget SelectBox Test",
 *       description: "Test Input for SelectBox",
 *       defaultValue: "dog",
 *       type: "string",
 *       widget: {
 *         type: "SelectBox",
 *         structure: [{
 *           key: "dog",
 *           label: "A Dog"
 *         }, {
 *           key: "cat",
 *           label: "A Cat"
 *         }]
 *       }
 *     },
 *   }
 * </pre>
 *
 * The default widgets for data types are as follows:
 *     string: text
 *     integer: spinner
 *     bool:  checkBox
 *     number: text
 *     data:  file-upload/selection
 *
 * The following widget types are supported:
 *     selectBox: { structure: [ {key: x, label: y}, ...] },
 *     date: { }, // following unix tradition, dates are represented in epoc seconds
 *     password: {},
 *     textArea: {},
 *     hiddenText: {},
 *     checkBox: {},
 *     comboBox: {},
 *
 *
 * Populate the new form using the setData method, providing a map
 * with the required data.
 *
 */

qx.Class.define("osparc.form.Auto", {
  extend: qx.ui.form.Form,
  include: [qx.locale.MTranslation],

  /**
    * @param structure {Object} form structure
    */
  construct: function(structure) {
    this.base(arguments);
    this.__ctrlMap = {};
    let formCtrl = this.__formCtrl = new qx.data.controller.Form(null, this);
    this.__boxCtrl = {};
    for (let key in structure) {
      this.__addField(structure[key], key);
    }
    let model = this.__model = formCtrl.createModel(true);

    model.addListener("changeBubble", e => {
      if (!this.__settingData) {
        this.fireDataEvent("changeData", this.getData());
      }
    },
    this);
  },

  events: {
    /**
     * fire when the form changes content and
     * and provide access to the data
     */
    "changeData": "qx.event.type.Data"
  },

  statics: {
    hasValidatableProp: function(s) {
      return Object.keys(s).some(r => ["minimum", "maximum"].includes(r));
    }
  },

  members: {
    __boxCtrl: null,
    __ctrlMap: null,
    __formCtrl: null,
    __model: null,
    __settingData: false,


    /**
     * Use normal Form validation to validate the content of the form
     *
     * @return {let} validation output
     */
    validate: function() {
      return this.__formCtrl.validate();
    },


    /**
     * Reset the form content
     *
     */
    reset: function() {
      this.__formCtrl.reset();
    },


    /**
     * get a handle to the control with the given name
     *
     * @param key {let} key of the the field
     * @return {let} control associated with the field
     */
    getControl: function(key) {
      return this.__ctrlMap[key];
    },

    getControls: function() {
      return this.__ctrlMap;
    },


    /**
     * fetch the data for this form
     *
     * @return {let} all data from the form
     */
    getData: function() {
      return this.__getData(this.__model);
    },

    /**
     * load new data into the data main model
     *
     * @param data {let} map with key value pairs to apply
     * @param relax {let} ignore non existing keys
     */
    setData: function(data, relax) {
      this.__setData(this.__model, data, relax);
    },


    /**
     * load new data into a model
     * if relax is set unknown properties will be ignored
     *
     * @param model {let} TODOC
     * @param data {let} TODOC
     * @param relax {let} TODOC
     */
    __setData: function(model, data, relax) {
      this.__settingData = true;

      for (let key in data) {
        // this.getControl(key).setEnabled(true);
        let upkey = qx.lang.String.firstUp(key);
        let setter = "set" + upkey;
        let value = data[key];
        if (relax && !model[setter]) {
          continue;
        }
        model[setter](value);
      }

      this.__settingData = false;

      /* only fire ONE if there was an attempt at change */
      this.fireDataEvent("changeData", this.getData());
    },


    /**
     * turn a model object into a plain data structure
     *
     * @param model {let} TODOC
     * @return {let} TODOC
     */
    __getData: function(model) {
      let props = model.constructor.$$properties;
      let data = {};

      for (let key in props) {
        let getter = "get" + qx.lang.String.firstUp(key);
        data[key] = model[getter]();
      }

      return data;
    },


    /**
     * set the data in a selectbox
     *
     * @param box {let} selectbox name
     * @param data {let} configuration of the box
     */
    setSelectBoxData: function(box, data) {
      let model;
      this.__settingData = true;

      if (data.length == 0) {
        model = qx.data.marshal.Json.createModel([{
          label: "",
          key: null
        }]);
      } else {
        model = qx.data.marshal.Json.createModel(data);
      }

      this.__boxCtrl[box].setModel(model);
      this.__boxCtrl[box].getTarget().resetSelection();
      this.__settingData = false;
    },

    __setupDateField: function(s) {
      this.__formCtrl.addBindingOptions(s.key,
        { // model2target
          converter: function(data) {
            if (/^\d+$/.test(String(data))) {
              let d = new Date();
              d.setTime(parseInt(data) * 1000);
              let d2 = new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 0, 0, 0, 0);
              return d2;
            }
            if (qx.lang.Type.isDate(data)) {
              return data;
            }
            return null;
          }
        },
        { // target2model
          converter: function(data) {
            if (qx.lang.Type.isDate(data)) {
              let d = new Date(Date.UTC(data.getFullYear(), data.getMonth(), data.getDate(), 0, 0, 0, 0));
              return Math.round(d.getTime()/1000);
            }
            return null;
          }
        }
      );
      s.set.dateFormat = new qx.util.format.DateFormat(
        this["tr"](
          s.set.dateFormat ?
            s.set.dateFormat :
            "dd.MM.yyyy"
        )
      );
      let dateValue = s.defaultValue;
      if (dateValue !== null) {
        if (typeof dateValue == "number") {
          s.defaultValue = new Date(dateValue * 1000);
        } else {
          s.defaultValue = new Date(dateValue);
        }
      }
    },
    __setupTextArea: function(s, key, control) {
      if (s.widget.minHeight) {
        control.setMinHeight(s.widget.minHeight);
      }
      this.__setupTextField(s, key, control);
    },
    __setupTextField: function(s, key) {
      this.__formCtrl.addBindingOptions(key,
        { // model2target
          converter: function(data) {
            return String(data);
          }
        },
        { // target2model
          converter: function(data) {
            return data;
          }
        }
      );
    },
    __setupNumberField: function(s, key) {
      if (s.defaultValue) {
        s.set.value = qx.lang.Type.isNumber(s.defaultValue) ? String(s.defaultValue) : s.defaultValue;
      } else {
        s.set.value = String(0);
      }
      const model2target = {
        converter: function(data) {
          if (qx.lang.Type.isNumber(data) && !isNaN(parseFloat(data))) {
            return String(data);
          }
          return null;
        }
      };
      const target2model = {
        myContext: {
          that: this,
          s,
          key
        },
        converter: function(data) {
          if (!data) {
            // this avoids the moustached template issue
            return parseFloat(s.defaultValue);
          }
          const tmp = data.split(" ");
          if (tmp.length > 1 && "x_unit" in this.myContext.s) {
            // extract unit with prefix from text
            const prefix = osparc.utils.Units.getPrefix(this.myContext.s["x_unit"], tmp[1]);
            if (prefix !== null) {
              // eslint-disable-next-line no-underscore-dangle
              const item = this.myContext.that.__ctrlMap[key];
              item.unitPrefix = prefix;
              osparc.form.renderer.PropFormBase.updateUnitLabelPrefix(item);
            }
          }
          return parseFloat(data);
        }
      };
      this.__formCtrl.addBindingOptions(key, model2target, target2model);
    },
    __setupSpinner: function(s, key) {
      s.set.maximum = s.maximum ? parseInt(s.maximum) : 10000;
      s.set.minimum = s.minimum ? parseInt(s.minimum) : -10000;
      s.set.value = s.defaultValue ? parseInt(String(s.defaultValue)) : 0;

      this.__formCtrl.addBindingOptions(key,
        { // model2target
          converter: function(data) {
            let d = String(data);
            if (/^\d+$/.test(d)) {
              return parseInt(d);
            }
            return null;
          }
        },
        { // target2model
          converter: function(data) {
            return parseInt(data);
          }
        }
      );
    },

    __setupSelectBox: function(s, key, control) {
      let controller = this.__boxCtrl[key] = new qx.data.controller.List(null, control, "label");
      controller.setDelegate({
        bindItem: function(ctrl, item, index) {
          ctrl.bindProperty("key", "model", null, item, index);
          ctrl.bindProperty("label", "label", null, item, index);
        }
      });
      // Content Schema
      if ("enum" in s) {
        const entries = [];
        s.enum.forEach(entry => {
          entries.push({
            label: entry.toString(),
            key: entry
          });
        });
        s.widget["structure"] = entries;
      }
      const cfg = s.widget;
      let items = cfg.structure;
      if (items) {
        items.forEach(item => {
          item.label = item.label || "";
        }, this);
      } else {
        items = [{
          label: "",
          key: null
        }];
      }
      if ("defaultValue" in s) {
        s.set.value = [s.defaultValue];
      }
      // Content Schema
      if ("default" in s) {
        s.set.value = [s.default];
      }
      let sbModel = qx.data.marshal.Json.createModel(items);
      controller.setModel(sbModel);
      control.setModelSelection(s.set.value);
    },
    __setupComboBox: function(s, key, control) {
      let ctrl = this.__boxCtrl[key] = new qx.data.controller.List(null, control);
      let cfg = s.cfg;
      if (cfg.structure) {
        cfg.structure.forEach(function(item) {
          item = item ? this["tr"](item):null;
        }, this);
      } else {
        cfg.structure = [];
      }
      let sbModel = qx.data.marshal.Json.createModel(cfg.structure);
      ctrl.setModel(sbModel);
    },
    __setupBoolField: function(s, key, control) {
      if (s.set.value && typeof s.set.value === "string") {
        s.set.value = Boolean(s.set.value.toLowerCase() === "true");
      }
      this.__formCtrl.addBindingOptions(key,
        { // model2target
          converter: function(data) {
            return data;
          }
        },
        { // target2model
          converter: function(data) {
            return data;
          }
        }
      );
    },
    __setupFileButton: function(s, key) {
      this.__formCtrl.addBindingOptions(key,
        { // model2target
          converter: function(data) {
            return String(data);
          }
        },
        { // target2model
          converter: function(data) {
            return data;
          }
        }
      );
    },
    __setupContentSchema: function(s, key, control) {
      control.setContentSchema(s.contentSchema);
    },

    __addField: function(s, key) {
      const control = this.__getField(s, key);

      this.__ctrlMap[key] = control;
      let option = {}; // could use this to pass on info to the form renderer
      this.add(control, s.label ? this["tr"](s.label) : null, null, key, null, option);
    },

    __getField: function(s, key) {
      if (s.type === "ref_contentSchema") {
        Object.assign(s, s.contentSchema);
      }

      if (!s.set) {
        s.set = {};
      }
      if ("defaultValue" in s) {
        s.set.value = s.defaultValue;
      }
      // Content Schema
      if ("default" in s) {
        s.set.value = s.default;
      }

      if (!s.widget) {
        let type = s.type;
        if (type.match(/^data:/)) {
          type = "data";
        }
        s.widget = {
          type: {
            string: "Text",
            integer: "Spinner",
            number: "Number",
            boolean: "CheckBox",
            data: "FileButton",
            array: "ArrayTextField",
            "ref_contentSchema": "ContentSchema"
          }[type]
        };
      }
      // Content Schema
      if ("enum" in s) {
        s.widget["type"] = "SelectBox";
      }
      let control;
      let setup;
      switch (s.widget.type) {
        case "Date":
          control = new qx.ui.form.DateField();
          setup = this.__setupDateField;
          break;
        case "Text":
          control = new qx.ui.form.TextField();
          setup = this.__setupTextField;
          break;
        case "Number":
          control = new qx.ui.form.TextField();
          setup = this.__setupNumberField;
          break;
        case "Spinner":
          control = new qx.ui.form.Spinner();
          setup = this.__setupSpinner;
          break;
        case "Password":
          control = new osparc.ui.form.PasswordField();
          setup = this.__setupTextField;
          break;
        case "TextArea":
          control = new qx.ui.form.TextArea();
          setup = this.__setupTextArea;
          break;
        case "CheckBox":
          control = new qx.ui.form.CheckBox();
          setup = this.__setupBoolField;
          break;
        case "SelectBox":
          control = new qx.ui.form.SelectBox();
          setup = this.__setupSelectBox;
          s.set["minWidth"] = 80;
          break;
        case "ComboBox":
          control = new qx.ui.form.ComboBox();
          setup = this.__setupComboBox;
          break;
        case "FileButton":
          control = new qx.ui.form.TextField();
          setup = this.__setupFileButton;
          break;
        case "ArrayTextField":
          control = new osparc.ui.form.ContentSchemaArray();
          setup = this.__setupContentSchema;
          break;
        default:
          throw new Error("unknown widget type " + s.widget.type);
      }

      setup.call(this, s, key, control);

      if (s.set) {
        if (s.set.filter) {
          s.set.filter = RegExp(s.filter);
        }
        if ("minimum" in s.set) {
          control.setMinimum(s.set["minimum"]);
        }
        if ("maximum" in s.set) {
          control.setMaximum(s.set["maximum"]);
        }
        control.set(s.set);
      }
      control.key = key;
      control.description = s.description;
      const rangeText = osparc.ui.form.ContentSchemaHelper.getDomainText(s);
      if (rangeText) {
        control.description += `<br>----<br>${rangeText}`;
      }
      control.type = s.type;
      control.widgetType = s.widget.type;
      control.unitShort = s.unitShort;
      control.unitLong = s.unitLong;
      if ("x_unit" in s) {
        const {
          unitPrefix,
          unit
        } = osparc.utils.Units.decomposeXUnit(s.x_unit);
        control.unitPrefix = unitPrefix;
        control.unit = unit;
      }

      let validator = null;
      if ("getValidator" in control) {
        validator = control.getValidator();
      } else if (this.self().hasValidatableProp(s)) {
        validator = osparc.ui.form.ContentSchemaHelper.createValidator(control, s);
      }
      if (validator) {
        control.addListener("changeValue", () => validator.validate());
      }

      return control;
    }
  }
});
