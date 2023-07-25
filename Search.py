import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from mmap import mmap, ACCESS_READ
import concurrent.futures
import multiprocessing


# Function to search a single file
def search_file(filename, search_text, file_extension):
    matches = []
    _, ext = os.path.splitext(filename)
    if file_extension == "*.*" or ext == file_extension:
        if search_text in filename:
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

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            future_to_file = {executor.submit(search_file, file, self.search_text, self.file_extension): file for file in self.files}
            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    searched_file, matches = future.result()
                    self.searched.append(searched_file)
                    self.results.extend(matches)
                except Exception as exc:
                    print(f'File {file} generated an exception: {exc}')


class ResultFrame(tk.Frame):
    def __init__(self, parent, result):
        tk.Frame.__init__(self, parent)
        self.result = result
        self.label = tk.Label(self, text=result)
        self.label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.button = tk.Button(self, text="Copy", command=self.copy)
        self.button.pack(side=tk.RIGHT)

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.result)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Austen's Fast File Search")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        for i in range(6):
            self.root.rowconfigure(i, weight=1 if i==4 else 0)

        self.label_search = tk.Label(self.root, text="Enter search text:")
        self.label_search.grid(row=0, column=0, sticky='ew')
        self.search_text = tk.StringVar()
        self.entry_search = tk.Entry(self.root, textvariable=self.search_text)
        self.entry_search.grid(row=1, column=0, sticky='ew')

        self.label_extension = tk.Label(self.root, text="Enter file extension:")
        self.label_extension.grid(row=2, column=0, sticky='ew')
        self.file_extension = tk.StringVar(value="*.*")
        self.entry_extension = tk.Entry(self.root, textvariable=self.file_extension)
        self.entry_extension.grid(row=3, column=0, sticky='ew')

        self.button = tk.Button(self.root, text="Search", command=self.search)
        self.button.grid(row=4, column=0, sticky='ew')

        self.progress = ttk.Progressbar(self.root)
        self.progress.grid(row=5, column=0, sticky='ew')

        self.label_results = tk.Label(self.root, text="Search results:")
        self.label_results.grid(row=6, column=0, sticky='ew')

        self.results_frame = tk.Frame(self.root)
        self.results_frame.grid(row=7, column=0, sticky='nsew')

        self.scrollbar = tk.Scrollbar(self.results_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results = tk.Listbox(self.results_frame, yscrollcommand=self.scrollbar.set)
        self.results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollbar.config(command=self.results.yview)

        self.label_searched = tk.Label(self.root, text="Searched files:")
        self.label_searched.grid(row=8, column=0, sticky='ew')

        self.searched = tk.Listbox(self.root)
        self.searched.grid(row=9, column=0, sticky='nsew')

    def search(self):
        directory = filedialog.askdirectory()
        search_text = self.search_text.get()
        file_extension = self.file_extension.get()
        self.results.delete(0, tk.END)
        self.searched.delete(0, tk.END)
        searcher = FileSearcherThread(directory, search_text, file_extension)
        searcher.start()
        self.root.after(100, self.check_thread, searcher)

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
            messagebox.showinfo("Search Complete", "The file search has been completed.")

root = tk.Tk()
app = App(root)
root.mainloop()
