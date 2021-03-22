/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * A singleton window is a type of window that can only have one instance.
 */
qx.Class.define("osparc.ui.window.SingletonWindow", {
  extend: osparc.ui.window.Window,

  construct: function(id, caption, icon) {
    this.setId(id);
    const singletonWindows = qx.core.Init.getApplication().getRoot()
      .getChildren()
      .filter(child => child.classname === this.classname);
    const thisWindow = singletonWindows.find(win => win.getId() === id);
    if (thisWindow) {
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
