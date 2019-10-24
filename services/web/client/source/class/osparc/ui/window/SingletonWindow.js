/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.window.SingletonWindow", {
  extend: qx.ui.window.Window,

  construct: function(id, caption, icon) {
    this.setId(id);
    const singletonWindows = qx.core.Init.getApplication().getRoot()
      .getChildren()
      .filter(child => child.classname === this.classname);
    const thisWindow = singletonWindows.find(win => win.getId() === id);
    if (thisWindow) {
      console.log(`Trying to create another SingletonWindow with id ${id}, disposing the old one...`);
      thisWindow.dispose();
    }
    this.base(arguments, caption, icon);
  },

  properties: {
    id: {
      check: "String",
      nullable: false
    }
  }
});
