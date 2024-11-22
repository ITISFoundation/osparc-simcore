/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ConsoleErrorTracker", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__errors = [];
  },

  members: {
    __errors: null,

    startTracker: function() {
      const originalConsoleError = console.error;

      // Override console.error
      console.error = (...args) => {
        this.__errors.unshift({
          date: new Date(),
          error: args
        });
        if (this.__errors.length > 20) {
          this.__errors.length = 20;
        }

        // Call the original console.error so the error still appears in the console
        originalConsoleError.apply(console, args);
      };
    },

    getErrors: function() {
      return this.__errors;
    },
  }
});
