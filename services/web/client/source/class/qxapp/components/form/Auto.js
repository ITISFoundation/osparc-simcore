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
 *     [
 *         {
 *           key: 'xyc',             // unique name
 *           label: 'label',
 *           type: string|integer|bool,
 *           widget: 'text',
 *           cfg: {},                // widget specific configuration
 *           set: {}                 // normal qx porperties to apply
 *          },
 *          ....
 *     ]
 *
 * The default widgets for data types are as follows:
 *
 *     string: text
 *     integer: spinner
 *     bool:  checkBox
 *
 * The following widgets are supported:
 *     header: { label: "header text"},
 *     text: { },
 *     selectBox: { cfg: { structure: [ {key: x, label: y}, ...] } },
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

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.form.Auto", {
  extend : qx.ui.form.Form,
  include : [qx.locale.MTranslation],

  /**
     * @param structure {Array} form structure
     */
  construct : function(content) {
    this.base(arguments);
    this.__ctrlMap = {};
    let formCtrl = this.__formCtrl = new qx.data.controller.Form(null, this);
    this.__boxCtrl = {};
    this.__typeMap = {};

    content.forEach(this.__addField, this);

    let model = this.__model = formCtrl.createModel(true);

    model.addListener("changeBubble", function(e) {
      if (!this.__settingData) {
        this.fireDataEvent("changeData", this.getData());
      }
    },
    this);
  },

  events : {
    /**
     * fire when the form changes content and
     * and provide access to the data
     */
    changeData : "qx.event.type.Data"
  },

  members : {
    __boxCtrl : null,
    __ctrlMap : null,
    __formCtrl: null,
    __model : null,
    __settingData : false,
    __typeMap : null,


    /**
     * Use normal Form validation to validate the content of the form
     *
     * @return {let} validation output
     */
    validate : function() {
      return this.__formCtrl.validate();
    },


    /**
     * Reset the form content
     *
     */
    reset : function() {
      this.__formCtrl.reset();
    },


    /**
     * get a handle to the control with the given name
     *
     * @param key {let} key of the the field
     * @return {let} control associated with the field
     */
    getControl : function(key) {
      return this.__ctrlMap[key];
    },


    /**
     * fetch the data for this form
     *
     * @return {let} all data from the form
     */
    getData : function() {
      return this.__getData(this.__model);
    },

    /**
     * load new data into the data main model
     *
     * @param data {let} map with key value pairs to apply
     * @param relax {let} ignore non existing keys
     */
    setData : function(data, relax) {
      this.__setData(this.__model, data, relax);
    },


    /**
     * set the data in a selectbox
     *
     * @param box {let} selectbox name
     * @param data {let} configuration of the box
     */
    setSelectBoxData : function(box, data) {
      let model;
      this.__settingData = true;

      if (data.length == 0) {
        model = qx.data.marshal.Json.createModel([{
          label : "",
          key   : null
        }]);
      } else {
        model = qx.data.marshal.Json.createModel(data);
      }

      this.__boxCtrl[box].setModel(model);
      this.__boxCtrl[box].getTarget().resetSelection();
      this.__settingData = false;
    },


    /**
     * load new data into a model
     * if relax is set unknown properties will be ignored
     *
     * @param model {let} TODOC
     * @param data {let} TODOC
     * @param relax {let} TODOC
     */
    __setData : function(model, data, relax) {
      this.__settingData = true;

      for (let key in data) {
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
    __getData : function(model) {
      let props = model.constructor.$$properties;
      let data = {};

      for (let key in props) {
        let getter = "get" + qx.lang.String.firstUp(key);
        data[key] = model[getter]();
      }

      return data;
    },
    __setupDateField: function(s) {
      this.__formCtrl.addBindingOptions(s.key,
        { // model2target
          converter : function(data) {
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
          converter : function(data) {
            if (qx.lang.Type.isDate(data)) {
              let d = new Date(Date.UTC(data.getFullYear(), data.getMonth(), data.getDate(), 0, 0, 0, 0));
              return Math.round(d.getTime()/1000);
            }
            return null;
          }
        }
      );
      if (!s.set) {
        s.set = {};
      }
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
    __setupTextField: function(s) {
      this.__formCtrl.addBindingOptions(s.key,
        { // model2target
          converter : function(data) {
            return String(data);
          }
        },
        { // target2model
          converter : function(data) {
            return data;
          }
        }
      );
    },
    __setupSpinner: function(s) {
      if (!s.set) {
        s.set = {};
      }
      if (s.defaultValue) {
        s.set.value = parseInt(s.defaultValue);
      }
      this.__formCtrl.addBindingOptions(s.key,
        { // model2target
          converter : function(data) {
            let d = String(data);
            if (/^\d+$/.test(d)) {
              return parseInt(d);
            }
            return null;
          }
        },
        { // target2model
          converter : function(data) {
            return parseInt(data);
          }
        }
      );
    },
    __setupSelectBox: function(s, control) {
      let controller = this.__boxCtrl[s.key] = new qx.data.controller.List(null, control, "label");
      controller.setDelegate({
        bindItem : function(ctrl, item, index) {
          ctrl.bindProperty("key", "model", null, item, index);
          ctrl.bindProperty("label", "label", null, item, index);
        }
      });
      let cfg = s.cfg;
      if (cfg.structure) {
        cfg.structure.forEach(function(item) {
          item.label = item.label ? this["tr"](item.label) : null;
        }, this);
      } else {
        cfg.strucuture = [{
          label : "",
          key   : null
        }];
      }
      if (s.set.value) {
        s.set.value = [s.set.value];
      }
      // console.log(cfg.structure);
      let sbModel = qx.data.marshal.Json.createModel(cfg.structure);
      controller.setModel(sbModel);
    },
    __setupComboBox: function(s, control) {
      let ctrl = this.__boxCtrl[s.key] = new qx.data.controller.List(null, control);
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
    __setupBoolField: function(s, control) {
      if (!s.set) {
        s.set = {};
      }
      if (s.defaultValue) {
        s.set.value = s.defaultValue;
      }
      this.__formCtrl.addBindingOptions(s.key,
        { // model2target
          converter : function(data) {
            return data;
          }
        },
        { // target2model
          converter : function(data) {
            return data;
          }
        }
      );
    },
    __setupFileButton: function(s) {
      this.__formCtrl.addBindingOptions(s.key,
        { // model2target
          converter : function(data) {
            return String(data);
          }
        },
        { // target2model
          converter : function(data) {
            return data;
          }
        }
      );
    },
    __addField: function(s) {
      // FIXME: OM why null?
      if (s === null) {
        return;
      }
      let option = {
        exposable: s.exposable
      }; // for passing info into the form renderer

      if (s.widget == "header") {
        this.addGroupHeader(s.label ? this["tr"](s.label):null, option);
        return;
      }

      if (!s.key) {
        throw new Error("the key property is required");
      }
      if (s.defaultValue) {
        if (!s.set) {
          s.set = {};
        }
        s.set.value = s.defaultValue;
      }
      // FIXME: This should go away
      if (s.value) {
        if (!s.set) {
          s.set = {};
        }
        s.set.value = s.value;
      }
      if (!s.widget) {
        s.widget = {
          string: "text",
          integer: "spinner",
          number: "spinner",
          bool: "checkBox",
          "file-url": "fileButton",
          "folder-url": "fileButton"
        }[s.type];
      }
      let control;
      let setup;
      switch (s.widget) {
        case "date":
          control = new qx.ui.form.DateField();
          setup = this.__setupDateField;
          break;
        case "text":
          control = new qx.ui.form.TextField();
          setup = this.__setupTextField;
          break;
        case "spinner":
          control = new qx.ui.form.Spinner();
          control.set({
            maximum: 10000,
            minimum: -10000
          });
          setup = this.__setupSpinner;
          break;
        case "password":
          control = new qx.ui.form.PasswordField();
          setup = this.__setupTextField;
          break;
        case "textArea":
          control = new qx.ui.form.TextArea();
          setup = this.__setupTextField;
          break;
        case "hiddenText":
          control = new qx.ui.form.TextField();
          control.exclude();
          setup = this.__setupTextField;
          break;
        case "checkBox":
          control = new qx.ui.form.CheckBox();
          setup = this.__setupBoolField;
          break;
        case "selectBox":
          control = new qx.ui.form.SelectBox();
          setup = this.__setupSelectBox;
          break;
        case "comboBox":
          control = new qx.ui.form.ComboBox();
          setup = this.__setupComboBox;
          break;
        case "fileButton":
          control = new qx.ui.form.TextField();
          setup = this.__setupFileButton;
          break;
        default:
          throw new Error("unknown widget type " + s.widget);
      }
      this.__ctrlMap[s.key] = control;
      this.add(control, s.label ? this["tr"](s.label):null, null, s.key, null, option);

      setup.call(this, s, control);

      if (s.set) {
        if (s.set.filter) {
          s.set.filter = RegExp(s.filter);
        }
        if (s.set.placeholder) {
          s.set.placeholder = this["tr"](s.set.placeholder);
        }
        if (s.set.label) {
          s.set.label = this["tr"](s.set.label);
        }
        console.log(s.set);
        control.set(s.set);
      }
      this.__ctrlMap[s.key] = control;
    }
  }
});
