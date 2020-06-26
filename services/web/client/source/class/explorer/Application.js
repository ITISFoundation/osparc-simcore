/* ************************************************************************

   explorer - an entry point to oSparc

   https://osparc.io/explorer

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * This is the main application class of "explorer"
 *
 * @asset(explorer/*)
 * @asset(common/common.css)
 */

qx.Class.define("explorer.Application", {
  extend: qx.application.Standalone,
  include: [
    qx.locale.MTranslation
  ],

  members: {
    /**
     * This method contains the initial application code and gets called
     * during startup of the application
     */
    main: function() {
      // Call super class
      this.base();

      // Enable logging in debug variant
      if (qx.core.Environment.get("qx.debug")) {
        // support native logging capabilities, e.g. Firebug for Firefox
        qx.log.appender.Native;
      }

      this.__loadMainPage();
    },

    __loadMainPage: function() {
      const padding = 0;
      const view = new explorer.MainPage();
      const doc = this.getRoot();
      doc.add(view, {
        top: padding,
        bottom: padding,
        left: padding,
        right: padding
      });
    }
  }
});
