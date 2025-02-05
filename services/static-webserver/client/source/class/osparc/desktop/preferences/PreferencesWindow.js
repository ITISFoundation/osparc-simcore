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

qx.Class.define("osparc.desktop.preferences.PreferencesWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "preferences", this.tr("Preferences"));

    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "preferencesWindowCloseBtn");

    const width = 750;
    const height = 660;
    this.set({
      width,
      height
    });

    const preferences = this.__preferences = new osparc.desktop.preferences.Preferences();
    this._setTabbedView(preferences);
  },

  statics: {
    openWindow: function() {
      const preferencesWindow = new osparc.desktop.preferences.PreferencesWindow();
      preferencesWindow.center();
      preferencesWindow.open();
      return preferencesWindow;
    }
  },

  members: {
    __preferences: null,

    openTags: function() {
      return this.__preferences.openTags();
    }
  }
});
