/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Andrei Neagu (GitHK)

************************************************************************ */

/**
 * Automatically expire keys after ttl (time to live) is reached
 */
qx.Class.define("osparc.data.TTLMap", {
  extend: qx.core.Object,

  /**
    * @param ttl time for which to keep track of the entries
    */
  construct: function(ttl) {
    this.base(arguments);

    this._entries = new Map();
    this._ttl = ttl;
  },

  members: {

    /**
     * @param {object} entry: add an entry or extend it's duration
     */
    addOrUpdateEntry: function(entry) {
      const now = Date.now();
      console.log("mapping", entry, "to", now);
      this._entries.set(entry, now);

      // Set a timeout to potentially remove the entry after the ttl if it's the latest
      setTimeout(() => {
        // If the entry is still the latest, remove it
        if (now === this._entries.get(entry)) {
          this._entries.delete(entry);
        }
      }, this._ttl);
    },

    /**
     * checks of the entry is still present and valid (did not reach the `ttl`)
     * @param {*} entry
     * @returns
     */
    hasRecentEntry: function(entry) {
      const now = Date.now();
      if (this._entries.has(entry)) {
        const lastUpdate = this._entries.get(entry);
        return now - lastUpdate <= this._ttl;
      }
      return false;
    }

  }
});
