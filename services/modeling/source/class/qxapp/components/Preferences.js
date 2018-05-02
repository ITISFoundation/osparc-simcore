qx.Class.define("qxapp.components.Preferences", {
  extend: qx.ui.window.Window,

  include : [qx.locale.MTranslation],

  construct : function(model, width, height, backgroundColor, fontColor) {
    this.base(arguments, this.tr("Preferences"));

    this._model = model;

    this.set({
      // contentPadding: 0,
      // width: width,
      // height: height,
      // allowClose: false,
      allowMinimize: false,
      backgroundColor: backgroundColor,
      textColor: fontColor,
      modal: true
    });
    this.setLayout(new qx.ui.layout.Grow());

    // this.setLayout(new qx.ui.layout.VBox);
    let container = new qx.ui.container.Composite(new qx.ui.layout.Basic());

    let options_form = this._createOptions();
    this._createButtons(options_form);
    // this.add(options_form);
    container.add(new qx.ui.form.renderer.Single(options_form), {
      left: 10,
      top: 10
    });

    this.add(container);
  },

  events : {},

  members: {
    _model: null,

    _createOptions : function() {
      let form = new qx.ui.form.Form();


      // Translation && Localization
      let localeManager = qx.locale.Manager.getInstance();
      let locales = localeManager.getAvailableLocales().sort();
      let currentLocale = localeManager.getLocale();

      let localeBox = new qx.ui.form.SelectBox({
        width: 100,
        allowGrowY: false
      });
      localeBox.setTextColor("black");
      let defaultListItem = this._model.getLocaleCode();
      for (let i=0; i<locales.length; i++) {
        let listItem = new qx.ui.form.ListItem(locales[i]);
        localeBox.add(listItem);
        if ((!defaultListItem && locales[i] == "en") || locales[i] == currentLocale) {
          defaultListItem = listItem;
        }
      }
      localeBox.addListener("changeSelection", function(e) {
        let locale = e.getData()[0].getLabel();
        qx.locale.Manager.getInstance().setLocale(locale);
        this._model.setLocaleCode(locale);
      }, this);
      if (defaultListItem) {
        localeBox.setSelection([defaultListItem]);
      }
      form.add(localeBox, this.tr("Language"));


      // FormAndListController
      let userBox = new qx.ui.form.SelectBox();
      userBox.setTextColor("black");
      let userController = new qx.data.controller.List(null, userBox);
      userController.setDelegate({
        bindItem: function(controller, item, index) {
          controller.bindProperty("Name", "label", null, item, index);
          controller.bindProperty("ID", "model", null, item, index);
        }
      });
      userController.setModel(this._model.getUsers());
      for (let i = 0; i < userBox.getSelectables().length; i++) {
        if (userBox.getSelectables()[i].getModel() === this._model.getActiveUser()) {
          userBox.setSelection([userBox.getSelectables()[i]]);
          break;
        }
      }
      userBox.addListener("changeSelection", function(e) {
        let userId = e.getData()[0].getModel();
        this._model.setActiveUser(userId);
      }, this);
      form.add(userBox, this.tr("User"));


      let useExternalModeler = this._model.getUseExternalModeler();
      let useExternalModelerBox = new qx.ui.form.CheckBox();
      useExternalModelerBox.setValue(Boolean(useExternalModeler));
      useExternalModelerBox.addListener("changeValue", function(e) {
        let useExternal = e.getData();
        this._model.setUseExternalModeler(useExternal);
      }, this);
      form.add(useExternalModelerBox, this.tr("Use external modeler"));


      let exportSceneAsBinary = this._model.getExportSceneAsBinary();
      let exportSceneAsBinaryBox = new qx.ui.form.CheckBox();
      exportSceneAsBinaryBox.setValue(Boolean(exportSceneAsBinary));
      exportSceneAsBinaryBox.addListener("changeValue", function(e) {
        let useBinary = e.getData();
        this._model.setExportSceneAsBinary(useBinary);
      }, this);
      form.add(exportSceneAsBinaryBox, this.tr("Export scenes in binary format"));


      return form;
    },

    _createButtons : function(options_form) {
      const btnWidth = 120;

      let cancelBtn = new qx.ui.form.Button(this.tr("Cancel"));
      cancelBtn.setWidth(btnWidth);
      cancelBtn.setTextColor("black");
      cancelBtn.addListener("execute", function(e) {
        this._CloseWindow(0);
      }, this);
      options_form.addButton(cancelBtn);

      let saveBtn = new qx.ui.form.Button(this.tr("Accept"));
      saveBtn.setWidth(btnWidth);
      saveBtn.setTextColor("black");
      saveBtn.addListener("execute", function(e) {
        this._CloseWindow(1);
      }, this);
      options_form.addButton(saveBtn);
    },

    _CloseWindow : function(code) {
      this._closeStatus = code;
      this.close();
    }
  }
});
