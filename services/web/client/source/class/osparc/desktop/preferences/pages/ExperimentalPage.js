/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 * Experimental Misc in preferences dialog
 *
 *
 */

qx.Class.define("osparc.desktop.preferences.pages.ExperimentalPage", {
  extend:osparc.desktop.preferences.pages.BasePage,

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

      let label = this._createHelpLabel(this.tr(
        "This is a list of experimental themes for the UI. By default the \
         osparc-theme is selected"
      ));
      box.add(label);

      let linkBtn = new osparc.ui.form.LinkButton(this.tr("To qx-osparc-theme"), "https://github.com/ITISFoundation/qx-osparc-theme");
      box.add(linkBtn);

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
