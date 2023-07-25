import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from mmap import mmap, ACCESS_READ
import concurrent.futures
import multiprocessing
import re


# Function to search a single file
def search_file(filename, search_text, file_extension):
    matches = []
    _, ext = os.path.splitext(filename)
    if file_extension == "*.*" or re.fullmatch(file_extension, ext):
        if search_text.lower() in filename.lower():
            matches.append(filename)
        else:
            with open(filename, 'r', errors='ignore') as f:
                try:
                    with mmap(f.fileno(), 0, access=ACCESS_READ) as s:
                        if s.find(bytes(search_text, 'utf-8')) != -1:
                            matches.append(filename)
                except ValueError:
                    pass
    return filename, matches


class SearchQueue:
    def __init__(self):
        self.queue = []
        self.current_search = None

    def add_search(self, directory, search_text, file_extension):
        self.queue.append((directory, search_text, file_extension))

    def next_search(self):
        if self.queue:
            return self.queue.pop(0)
        else:
            return None

    def is_searching(self):
        return self.current_search is not None and self.current_search.is_alive()

    def cancel_current_search(self):
        if self.is_searching():
            self.current_search.cancel_search()


class FileSearcherThread(threading.Thread):
    def __init__(self, directory, search_text, file_extension):
        threading.Thread.__init__(self)
        self.directory = directory
        self.search_text = search_text
        self.file_extension = file_extension
        self.files = []
        for foldername, subfolders, filenames in os.walk(directory):
            for filename in filenames:
                self.files.append(os.path.join(foldername, filename))
        self.results = []
        self.searched = []
        self.cancelled = False

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            future_to_file = {executor.submit(search_file, file, self.search_text, self.file_extension): file for file in self.files}
            for future in concurrent.futures.as_completed(future_to_file):
                if self.cancelled:
                    return
                file = future_to_file[future]
                try:
                    searched_file, matches = future.result()
                    self.searched.append(searched_file)
                    self.results.extend(matches)
                except Exception as exc:
                    print(f'File {file} generated an exception: {exc}')

    def cancel_search(self):
        self.cancelled = True


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Austen's Fast File Search")

        self.label_search = tk.Label(self.root, text="Enter search text:")
        self.label_search.pack(fill='x')
        self.search_text = tk.StringVar()
        self.entry_search = tk.Entry(self.root, textvariable=self.search_text)
        self.entry_search.pack(fill='x')

        self.label_extension = tk.Label(self.root, text="Enter file extension:")
        self.label_extension.pack(fill='x')
        self.file_extension = tk.StringVar(value="*.*")
        self.entry_extension = tk.Entry(self.root, textvariable=self.file_extension)
        self.entry_extension.pack(fill='x')

        self.button = tk.Button(self.root, text="Search", command=self.search)
        self.button.pack(fill='x')

        self.progress = ttk.Progressbar(self.root)
        self.progress.pack(fill='x')

        self.label_results = tk.Label(self.root, text="Search results:")
        self.label_results.pack(fill='x')

        self.results = tk.Listbox(self.root)
        self.results.pack(fill='both', expand=True)
        self.results.bind('<<ListboxSelect>>', self.copy_to_clipboard)

        self.label_searched = tk.Label(self.root, text="Searched files:")
        self.label_searched.pack(fill='x')

        self.searched = tk.Listbox(self.root)
        self.searched.pack(fill='both', expand=True)

        self.label_queue = tk.Label(self.root, text="Search queue:")
        self.label_queue.pack(fill='x')

        self.queue = tk.Listbox(self.root)
        self.queue.pack(fill='both', expand=True)

        self.queue_up_button = tk.Button(self.root, text="Move Up in Queue", command=self.move_up_in_queue)
        self.queue_up_button.pack(fill='x')

        self.queue_down_button = tk.Button(self.root, text="Move Down in Queue", command=self.move_down_in_queue)
        self.queue_down_button.pack(fill='x')

        self.queue_remove_button = tk.Button(self.root, text="Remove from Queue", command=self.remove_from_queue)
        self.queue_remove_button.pack(fill='x')

        self.search_queue = SearchQueue()

    def search(self):
        if self.search_queue.is_searching():
            self.search_queue.cancel_current_search()
            self.button.configure(text="Search")
        else:
            directory = filedialog.askdirectory()
            search_text = self.search_text.get()
            file_extension = self.file_extension.get()
            self.search_queue.add_search(directory, search_text, file_extension)
            self.queue.insert(tk.END, f"{search_text} in {directory} ({file_extension})")
            self.check_queue()
            self.button.configure(text="Cancel")

    def check_thread(self, thread):
        self.progress['value'] = len(thread.searched)
        self.progress['maximum'] = len(thread.files)
        for file in thread.searched[self.searched.size():]:
            self.searched.insert(tk.END, file)
        if thread.is_alive():
            self.root.after(100, self.check_thread, thread)
        else:
            for result in thread.results:
                self.results.insert(tk.END, result)
            self.queue.delete(0)
            self.check_queue()

    def check_queue(self):
        if not self.search_queue.is_searching():
            next_search = self.search_queue.next_search()
            if next_search:
                directory, search_text, file_extension = next_search
                searcher = FileSearcherThread(directory, search_text, file_extension)
                self.search_queue.current_search = searcher
                searcher.start()
                self.root.after(100, self.check_thread, searcher)
            else:
                self.button.configure(text="Search")
                messagebox.showinfo("Search Complete", "The file search has been completed.")

    def move_up_in_queue(self):
        selected = self.queue.curselection()
        if selected:
            for index in selected:
                if index != 0:
                    value = self.queue.get(index)
                    self.queue.delete(index)
                    self.queue.insert(index - 1, value)
                    self.queue.selection_set(index - 1)

    def move_down_in_queue(self):
        selected = self.queue.curselection()
        if selected:
            for index in reversed(selected):
                if index != self.queue.size() - 1:
                    value = self.queue.get(index)
                    self.queue.delete(index)
                    self.queue.insert(index + 1, value)
                    self.queue.selection_set(index + 1)

    def remove_from_queue(self):
        selected = self.queue.curselection()
        if selected:
            for index in reversed(selected):
                self.queue.delete(index)

    def copy_to_clipboard(self, event):
        self.root.clipboard_clear()
        selection = event.widget.curselection()
        if selection:
            selected = event.widget.get(selection)
            self.root.clipboard_append(selected)


root = tk.Tk()
app = App(root)
root.mainloop()
