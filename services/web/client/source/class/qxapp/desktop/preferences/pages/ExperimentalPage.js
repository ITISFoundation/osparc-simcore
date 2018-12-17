/**
 * Experimental Misc in preferences dialog
 *
 *
 */
/* eslint no-warning-comments: "off" */
qx.Class.define("qxapp.desktop.preferences.pages.ExperimentalPage", {
  extend:qxapp.desktop.preferences.pages.BasePage,

  construct: function() {
    const iconSrc = "@FontAwesome5Solid/flask/24";
    const title = this.tr("Experimental");
    this.base(arguments, title, iconSrc);

    this.add(this.__createThemesSelector());
  },

  members: {

    __createThemesSelector: function() {
      // layout
      let box = this._createSectionBox("UI Theme");

      let label = this._createHelpLabel("This is a list of experimental themes for the UI. \
        By default the <a href=https://github.com/ITISFoundation/qx-osparc-theme>osparc-theme</a> is \
        selected");
      box.add(label);

      let select = new qx.ui.form.SelectBox("Theme");
      box.add(select);

      // fill w/ themes
      let themeMgr = qx.theme.manager.Meta.getInstance();
      let currentTheme = themeMgr.getTheme();

      let themes = qx.Theme.getAll();
      for (let key in themes) {
        let theme = themes[key];
        if (theme.type === "meta") {
          let item = new qx.ui.form.ListItem(theme.name);
          item.setUserData("theme", theme.name);
          select.add(item);
          if (theme.name == currentTheme.name) {
            select.setSelection([item]);
          }
        }
      }

      select.addListener("changeSelection", evt => {
        let selected = evt.getData()[0].getUserData("theme");
        let theme = qx.Theme.getByName(selected);
        if (theme) {
          themeMgr.setTheme(theme);
        }
      });
      return box;
    }

  }
});
