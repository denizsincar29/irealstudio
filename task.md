# task
Fix the error of the app not starting up with an UnboundLocalError.
```
Traceback (most recent call last):                                                                                      
  File "C:\Users\user\files\pythons\irealstudio\main.py", line 2291, in <module>                                        
    app.run()                                                                                                           
    ~~~~~~~^^                                                                                                           
  File "C:\Users\user\files\pythons\irealstudio\main.py", line 1728, in run                                             
    self.speak(_("IReal Studio ready. Press Ctrl+N for a new project or Ctrl+O to open a file."))                       
               ^                                                                                                        
UnboundLocalError: cannot access local variable '_' where it is not associated with a value
```

Carefully check the code and identify similar errors.
Make nuitka config to make the exe windowed if there is any nuitka config for the app, because changing py to pyw silents all the console output, which is not ideal for debugging when ran from the command line.