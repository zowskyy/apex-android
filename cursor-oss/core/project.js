// core/project.js - Save and load projects for intermittent power users
const fs = require('fs');
const path = require('path');

class ProjectManager {
  constructor(storageDir = '.cursor-oss-projects') {
    this.storageDir = storageDir;
    if (!fs.existsSync(storageDir)) {
      fs.mkdirSync(storageDir, { recursive: true });
    }
  }

  save(name, data) {
    const project = {
      name,
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
      files: data.files || {},
      history: data.history || [],
      idea: data.idea || '',
      status: data.status || 'in_progress'
    };

    const filePath = path.join(this.storageDir, `${name.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`);
    fs.writeFileSync(filePath, JSON.stringify(project, null, 2));
    return filePath;
  }

  load(name) {
    const filePath = path.join(this.storageDir, `${name.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`);
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  list() {
    return fs.readdirSync(this.storageDir)
      .filter(f => f.endsWith('.json'))
      .map(f => {
        const project = JSON.parse(fs.readFileSync(path.join(this.storageDir, f), 'utf-8'));
        return {
          name: project.name,
          created: project.created,
          updated: project.updated,
          status: project.status
        };
      });
  }

  delete(name) {
    const filePath = path.join(this.storageDir, `${name.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      return true;
    }
    return false;
  }
}

module.exports = { ProjectManager };
