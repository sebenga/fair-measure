import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { trigger, state, style, transition, animate } from '@angular/animations';
import { IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { 
  trashOutline, 
  cloudUploadOutline,
  checkmarkOutline,
  closeOutline 
} from 'ionicons/icons';

interface MediaFile {
  file: File;
  name: string;
  size: number;
  preview: string;
  uploading?: boolean;
  progress?: number;
  uploaded?: boolean;
}

@Component({
  selector: 'app-media-upload',
  templateUrl: './media-upload.component.html',
  styleUrls: ['./media-upload.component.scss'],
  standalone: true,
  animations: [
    trigger('fadeInUp', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(20px)' }),
        animate('300ms ease-out', style({ opacity: 1, transform: 'translateY(0)' }))
      ])
    ])
  ],
  imports: [
    CommonModule,
    IonIcon
  ]
})
export class MediaUploadComponent {
  @ViewChild('pictureInput') pictureInput!: ElementRef<HTMLInputElement>;
  @ViewChild('videoInput') videoInput!: ElementRef<HTMLInputElement>;

  pictureFiles: MediaFile[] = [];
  videoFiles: MediaFile[] = [];
  isDragOverPictures = false;
  isDragOverVideos = false;
  isUploading = false;

  // File size limits (in bytes)
  readonly MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10MB
  readonly MAX_VIDEO_SIZE = 100 * 1024 * 1024; // 100MB

  // Accepted file types
  readonly ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
  readonly ACCEPTED_VIDEO_TYPES = ['video/mp4', 'video/mov', 'video/avi', 'video/wmv', 'video/webm'];

  constructor() {
    addIcons({ 
      trashOutline, 
      cloudUploadOutline,
      checkmarkOutline,
      closeOutline 
    });
  }

  // Drag and Drop Handlers
  onDragOver(event: DragEvent, type: 'pictures' | 'videos'): void {
    event.preventDefault();
    event.stopPropagation();
    
    if (type === 'pictures') {
      this.isDragOverPictures = true;
    } else {
      this.isDragOverVideos = true;
    }
  }

  onDragLeave(event: DragEvent, type: 'pictures' | 'videos'): void {
    event.preventDefault();
    event.stopPropagation();
    
    if (type === 'pictures') {
      this.isDragOverPictures = false;
    } else {
      this.isDragOverVideos = false;
    }
  }

  onDrop(event: DragEvent, type: 'pictures' | 'videos'): void {
    event.preventDefault();
    event.stopPropagation();
    
    if (type === 'pictures') {
      this.isDragOverPictures = false;
    } else {
      this.isDragOverVideos = false;
    }

    const files = Array.from(event.dataTransfer?.files || []);
    this.processFiles(files, type);
  }

  // File Input Handlers
  triggerFileInput(type: 'pictures' | 'videos'): void {
    if (type === 'pictures') {
      this.pictureInput.nativeElement.click();
    } else {
      this.videoInput.nativeElement.click();
    }
  }

  onFileSelect(event: Event, type: 'pictures' | 'videos'): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files || []);
    this.processFiles(files, type);
    
    // Reset input value to allow selecting the same file again
    input.value = '';
  }

  // File Processing
  private processFiles(files: File[], type: 'pictures' | 'videos'): void {
    files.forEach(file => {
      if (this.validateFile(file, type)) {
        this.addFile(file, type);
      }
    });
  }

  private validateFile(file: File, type: 'pictures' | 'videos'): boolean {
    const isImage = type === 'pictures';
    const acceptedTypes = isImage ? this.ACCEPTED_IMAGE_TYPES : this.ACCEPTED_VIDEO_TYPES;
    const maxSize = isImage ? this.MAX_IMAGE_SIZE : this.MAX_VIDEO_SIZE;

    // Check file type
    if (!acceptedTypes.includes(file.type)) {
      this.showError(`Invalid file type: ${file.name}. Please select a valid ${type.slice(0, -1)} file.`);
      return false;
    }

    // Check file size
    if (file.size > maxSize) {
      const maxSizeMB = maxSize / (1024 * 1024);
      this.showError(`File too large: ${file.name}. Maximum size is ${maxSizeMB}MB.`);
      return false;
    }

    return true;
  }

  private addFile(file: File, type: 'pictures' | 'videos'): void {
    const mediaFile: MediaFile = {
      file,
      name: file.name,
      size: file.size,
      preview: '',
      uploading: false,
      progress: 0,
      uploaded: false
    };

    // Create preview
    this.createPreview(file, type).then(preview => {
      mediaFile.preview = preview;
      
      if (type === 'pictures') {
        this.pictureFiles.push(mediaFile);
      } else {
        this.videoFiles.push(mediaFile);
      }
    });
  }

  private createPreview(file: File, type: 'pictures' | 'videos'): Promise<string> {
    return new Promise((resolve) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        resolve(e.target?.result as string);
      };
      
      if (type === 'pictures') {
        reader.readAsDataURL(file);
      } else {
        // For videos, create object URL for preview
        const objectUrl = URL.createObjectURL(file);
        resolve(objectUrl);
      }
    });
  }

  // File Management
  removeFile(index: number, type: 'pictures' | 'videos'): void {
    if (type === 'pictures') {
      // Revoke object URL if it exists
      const file = this.pictureFiles[index];
      if (file.preview.startsWith('blob:')) {
        URL.revokeObjectURL(file.preview);
      }
      this.pictureFiles.splice(index, 1);
    } else {
      // Revoke object URL for videos
      const file = this.videoFiles[index];
      if (file.preview.startsWith('blob:')) {
        URL.revokeObjectURL(file.preview);
      }
      this.videoFiles.splice(index, 1);
    }
  }

  clearAllFiles(): void {
    // Revoke all object URLs
    [...this.pictureFiles, ...this.videoFiles].forEach(file => {
      if (file.preview.startsWith('blob:')) {
        URL.revokeObjectURL(file.preview);
      }
    });
    
    this.pictureFiles = [];
    this.videoFiles = [];
  }

  // Upload Functionality
  async uploadAllFiles(): Promise<void> {
    if (this.isUploading) return;

    this.isUploading = true;
    const allFiles = [...this.pictureFiles, ...this.videoFiles];

    try {
      // Upload files in parallel with progress tracking
      const uploadPromises = allFiles.map(mediaFile => this.uploadFile(mediaFile));
      await Promise.all(uploadPromises);
      
      this.showSuccess('All files uploaded successfully!');
      
      // Clear files after successful upload
      setTimeout(() => {
        this.clearAllFiles();
      }, 2000);
      
    } catch (error) {
      console.error('Upload error:', error);
      this.showError('Some files failed to upload. Please try again.');
    } finally {
      this.isUploading = false;
    }
  }

  private async uploadFile(mediaFile: MediaFile): Promise<void> {
    mediaFile.uploading = true;
    mediaFile.progress = 0;

    return new Promise((resolve, reject) => {
      // Simulate file upload with progress
      const interval = setInterval(() => {
        mediaFile.progress = (mediaFile.progress || 0) + Math.random() * 15;
        
        if (mediaFile.progress >= 100) {
          mediaFile.progress = 100;
          mediaFile.uploading = false;
          mediaFile.uploaded = true;
          clearInterval(interval);
          resolve();
        }
      }, 200);

      // Simulate potential upload failure (5% chance)
      if (Math.random() < 0.05) {
        setTimeout(() => {
          clearInterval(interval);
          mediaFile.uploading = false;
          reject(new Error(`Failed to upload ${mediaFile.name}`));
        }, 1000);
      }
    });
  }

  // Utility Functions
  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  private showError(message: string): void {
    // In a real app, you'd use a toast or notification service
    alert(message);
  }

  private showSuccess(message: string): void {
    // In a real app, you'd use a toast or notification service
    alert(message);
  }

  // Cleanup on component destroy
  ngOnDestroy(): void {
    // Revoke all object URLs to prevent memory leaks
    [...this.pictureFiles, ...this.videoFiles].forEach(file => {
      if (file.preview.startsWith('blob:')) {
        URL.revokeObjectURL(file.preview);
      }
    });
  }
}