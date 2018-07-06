qx.Class.define("qxapp.data.model.Project",
  {
    extend: qx.core.Object,

    properties: {
      id: {
        check: "String",
        event: "changeId",
        nullable: true
      },

      name: {
        check: "String",
        init: "Unnamed"
      },

      description: {
        check: "String",
        nullable: true
      },

      thumbnail: {
        check: "String",
        nullable: true
      },

      createdOn: {
        check: "Date",
        nullable: true
      }

    },

    members: {

      toString: function() {
        // return qx.dev.Debug.debugProperties(this, 3, false, 2);
        let newLine = "\n";
        let indent = 4;
        let html = false;
        const maxLevel = 5;
        let message = "";

        let properties = this.constructor.$$properties;
        for (let key in properties) {
          message += newLine;
          // print out the indentation
          for (var j = 0; j < indent; j++) {
            message += "-";
          }
          message += " " + key + ": " + this.toString(
            this["get" + qx.lang.String.firstUp(key)](), maxLevel - 1, html, indent + 1
          );
        }
        return message;
      }

    }

  });
