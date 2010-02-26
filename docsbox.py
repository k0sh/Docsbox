#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import ConfigParser

import gdata.docs.service

def entry_updated(entry):
    """ Возвращает время последнего обновления документа в секундах с начала эпохи """
    t = time.strptime(entry.updated.text, "%Y-%m-%dT%H:%M:%S.%fZ")
    return time.mktime(t)

def update_filetime(fpath, entry):
    """ Устанавливает время модификации файла равное дате последнего обновления документа """
    print "  Updating modifed time..."
    updated = entry_updated(entry)
    os.utime(fpath, (updated, updated))

def download(client, entry, boxdir):
    """  Загружает документ из Google Docs в папку """
    doc = entry.title.text.decode('utf-8')
    print "  Downloading document <%s>..." % doc
    fpath = os.path.join(boxdir, (doc+".doc"))
    client.Export(entry, fpath)
    update_filetime(fpath, entry)

def upload(client, folder, doc, fpath):
    """ Загружает локальный документ в Google Docs """
    print "  Uploading document <%s>..." % doc
    ms = gdata.MediaSource(file_path=fpath, content_type=gdata.docs.service.SUPPORTED_FILETYPES['DOC'])
    entry = client.Upload(ms, doc, folder_or_uri=folder)
    update_filetime(fpath, entry)

def update(client, entry, fpath):
    """ Обновляет документ содержимым указанного файла (fpath) """
    doc = entry.title.text.decode('utf-8')
    print "  Updating document <%s>..." % doc
    ms = gdata.MediaSource(file_path=fpath, content_type=gdata.docs.service.SUPPORTED_FILETYPES['DOC'])
    updated_entry = client.Put(ms, entry.GetEditMediaLink().href)
    update_filetime(fpath, updated_entry)

def get_google_documents(client, folder):
    """ Возвращает словарь документов Google Docs в папке folder """
    documents = {}
    query = gdata.docs.service.DocumentQuery(categories=[folder, 'document'])
    feed = client.Query(query.ToUri())
    for entry in feed.entry:
        documents[entry.title.text.decode('utf-8')] = entry
    return documents

def get_local_documents(boxdir):
    """ Возвращает словарь документов в директории boxdir """
    local_documents = {}
    files = os.listdir(boxdir)
    for fname in filter(lambda fname: os.path.splitext(fname)[1] in ['.doc'], files):
        name, ext = os.path.splitext(fname)
        local_documents[name] = os.path.join(boxdir, fname)
    return local_documents

def get_google_folders(client):
    """ Возвращает словарь папок из Google Docs """
    folders = {}
    query = gdata.docs.service.DocumentQuery(categories=['folder'], params = {'showfolders':'true'})
    feed = client.Query(query.ToUri())
    assert feed.entry != None
    for entry in feed.entry:
        folders[entry.title.text.decode('utf-8')] = entry
    return folders

def main():
    print "Loading settings..."
    config = ConfigParser.ConfigParser()
    config.read("docsbox.conf")
    
    try:
        GMAIL = config.get("main", "GMAIL")
        PASSWORD = config.get("main", "PASSWORD")
        BOX_PATH = config.get("main", "BOX_PATH")
        FOLDER = config.get("main", "FOLDER", "dropbox")
    except ConfigParser.NoSectionError:
        print >>sys.stderr, "Error: Wrong configuration file format"
        sys.exit(-1)

    print "Attempting login as %s..." % GMAIL
    client = gdata.docs.service.DocsService()
    try:
        client.ClientLogin(GMAIL, PASSWORD, source="Docsbox 0.1")
    except gdata.service.BadAuthentication:
        print >>sys.stderr, " Invalid user credentials given."
        sys.exit(-1)

    print "Getting folders list..."
    folders = get_google_folders(client)

    if not folders.has_key(FOLDER):
        print "Attempting to create folder..."
        f = client.CreateFolder(FOLDER)
        if not f:
            print "...[FAIL]"
            sys.exit(-1)
        folders[FOLDER] = f
    
    print "Getting documents list..."
    google_documents = get_google_documents(client, FOLDER)

    print "Getting files list..."
    local_documents = get_local_documents(BOX_PATH)

    print "Syncing with Google documents..."
    for doc, entry in google_documents.items():
        if not local_documents.has_key(doc):
            print " Found a new document <%s>..." % doc
            download(client, entry, BOX_PATH)
        else:
            fpath = local_documents[doc]
            google_updated = entry_updated(entry)
            local_updated = os.path.getmtime(fpath)
            if google_updated > local_updated:
                print " Found updated document <%s>..." % doc
                download(client, entry, BOX_PATH)
            elif google_updated < local_updated:
                print " Found an old document <%s>..." % doc
                update(client, entry, fpath)
          
    print "Checking new local documents..."
    for doc, fpath in local_documents.items():
        if not google_documents.has_key(doc):
            folder = folders[FOLDER]
            upload(client, folder, doc, fpath)
    

if __name__ == "__main__":
    main()
