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

qx.Class.define("osparc.component.form.Auto", {
  extend: qx.ui.form.Form,
  include: [qx.locale.MTranslation],

  /**
     * @param structure {Array} form structure
     */
  construct: function(content, node) {
    // node is necessary for creating links
    if (node) {
      this.setNode(node);
    } else {
      this.setNode(null);
    }

    this.base(arguments);
    this.__ctrlMap = {};
    this.__ctrlLinkMap = {};
    let formCtrl = this.__formCtrl = new qx.data.controller.Form(null, this);
    this.__boxCtrl = {};
    this.__typeMap = {};
    for (let key in content) {
      this.__addField(content[key], key);
    }
    let model = this.__model = formCtrl.createModel(true);

    model.addListener("changeBubble", e => {
      if (!this.__settingData) {
        this.fireDataEvent("changeData", this.getData());
      }
    },
    this);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  events: {
    /**
     * fire when the form changes content and
     * and provide access to the data
     */
    "changeData": "qx.event.type.Data",
    "linkAdded": "qx.event.type.Data",
    "linkRemoved": "qx.event.type.Data"
  },

  members: {
    __boxCtrl: null,
    __ctrlMap: null,
    __ctrlLinkMap: null,
    __formCtrl: null,
    __model: null,
    __settingData: false,
    __typeMap: null,


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

    getControlLink: function(key) {
      return this.__ctrlLinkMap[key];
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
     * set access level to the data main model
     *
     * @param data {let} map with key access level pairs to apply
     */
    setAccessLevel: function(data) {
      this.__setAccessLevel(this.__model, data);
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
        if (data[key] !== null && typeof data[key] === "object" && data[key].nodeUuid) {
          this.addLink(key, data[key].nodeUuid, data[key].output);
          continue;
        }
        this.getControl(key).setEnabled(true);
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
     * set access level to the data model
     *
     * @param model {let} TODOC
     * @param data {let} TODOC
     */
    __setAccessLevel: function(model, data) {
      this.__settingData = true;

      for (const key in data) {
        const control = this.getControl(key);
        if (control) {
          switch (data[key]) {
            case "Invisible": {
              control.setEnabled(false);
              control.setVisibility("excluded");
              break;
            }
            case "ReadOnly": {
              control.setEnabled(false);
              control.setVisibility("visible");
              break;
            }
            case "ReadAndWrite": {
              control.setEnabled(true);
              control.setVisibility("visible");
              break;
            }
          }
        }
      }

      this.__settingData = false;

      /* only fire ONE if there was an attempt at change */

      this.fireDataEvent("changeData", this.getData());
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
      if (!s.set) {
        s.set = {};
      }
      if (s.defaultValue) {
        s.set.value = qx.lang.Type.isNumber(s.defaultValue) ? String(s.defaultValue) : s.defaultValue;
      } else {
        s.set.value = String(0);
      }
      this.__formCtrl.addBindingOptions(key,
        { // model2target
          converter: function(data) {
            if (qx.lang.Type.isNumber(data)) {
              return String(data);
            }
            return data;
          }
        },
        { // target2model
          converter: function(data) {
            return parseFloat(data);
          }
        }
      );
    },
    __setupSpinner: function(s, key) {
      if (!s.set) {
        s.set = {};
      }
      if (s.defaultValue) {
        s.set.value = parseInt(String(s.defaultValue));
      } else {
        s.set.value = 0;
      }
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
      let cfg = s.widget;
      if (cfg.structure) {
        cfg.structure.forEach(function(item) {
          item.label = item.label ? this["tr"](item.label) : null;
        }, this);
      } else {
        cfg.structure = [{
          label: "",
          key: null
        }];
      }
      if (s.defaultValue) {
        s.set.value = [s.defaultValue];
      }
      let sbModel = qx.data.marshal.Json.createModel(cfg.structure);
      controller.setModel(sbModel);
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
      if (!s.set) {
        s.set = {};
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
    __addField: function(s, key) {
      const control = this.__getField(s, key);

      this.__ctrlMap[key] = control;
      let option = {}; // could use this to pass on info to the form renderer
      this.add(control, s.label ? this["tr"](s.label) : null, null, key, null, option);

      let controlLink = new qx.ui.form.TextField().set({
        enabled: false
      });
      controlLink.key = key;
      this.__ctrlLinkMap[key] = controlLink;
    },

    __getField: function(s, key) {
      if (s.defaultValue) {
        if (!s.set) {
          s.set = {};
        }
        s.set.value = s.defaultValue;
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
            data: "FileButton"
          }[type]
        };
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
          control.set({
            maximum: 10000,
            minimum: -10000
          });
          setup = this.__setupSpinner;
          break;
        case "Password":
          control = new qx.ui.form.PasswordField();
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
          break;
        case "ComboBox":
          control = new qx.ui.form.ComboBox();
          setup = this.__setupComboBox;
          break;
        case "FileButton":
          control = new qx.ui.form.TextField();
          setup = this.__setupFileButton;
          break;
        default:
          throw new Error("unknown widget type " + s.widget.type);
      }

      setup.call(this, s, key, control);

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
        control.set(s.set);
      }
      control.key = key;
      control.description = s.description;

      return control;
    },

    isPortAvailable: function(portId) {
      const port = this.getControl(portId);
      if (!port || !port.getEnabled() || Object.prototype.hasOwnProperty.call(port, "link")) {
        return false;
      }
      return true;
    },

    addLink: function(toPortId, fromNodeId, fromPortId) {
      if (!this.isPortAvailable(toPortId)) {
        return false;
      }
      this.getControl(toPortId).setEnabled(false);
      this.getControl(toPortId).link = {
        nodeUuid: fromNodeId,
        output: fromPortId
      };

      const study = osparc.store.Store.getInstance().getCurrentStudy();
      const workbench = study.getWorkbench();
      const fromNode = workbench.getNode(fromNodeId);
      const port = fromNode.getOutput(fromPortId);
      const fromPortLabel = port ? port.label : null;
      fromNode.bind("label", this.getControlLink(toPortId), "value", {
        converter: label => label + ": " + fromPortLabel
      });

      this.fireDataEvent("linkAdded", toPortId);

      return true;
    },

    removeLink: function(toPortId) {
      this.getControl(toPortId).setEnabled(true);
      if ("link" in this.getControl(toPortId)) {
        delete this.getControl(toPortId).link;
      }

      this.fireDataEvent("linkRemoved", toPortId);
    }
  }
});
